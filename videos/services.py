import os
import subprocess
import threading
import json
from pathlib import Path

from django.conf import settings
from .models import Video

# Define target configurations
RESOLUTION_SETTINGS = [
    {"name": "240p", "width": 426, "height": 240, "v_bitrate": "600k", "a_bitrate": "64k"},
    {"name": "360p", "width": 640, "height": 360, "v_bitrate": "1100k", "a_bitrate": "96k"}, # Bumped up from 800k
    {"name": "480p", "width": 854, "height": 480, "v_bitrate": "2000k", "a_bitrate": "128k"}, # Bumped up from 1400k
    {"name": "720p", "width": 1280, "height": 720, "v_bitrate": "3500k", "a_bitrate": "128k"},
    {"name": "1080p", "width": 1920, "height": 1080, "v_bitrate": "6000k", "a_bitrate": "192k"},
    {"name": "4k", "width": 3840, "height": 2160, "v_bitrate": "22000k", "a_bitrate": "256k"},
]

def get_video_metadata(raw_video_path):
    """Extract duration, width, and height using FFprobe."""
    ffprobe_cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height:format=duration",
        "-of", "json",
        raw_video_path,
    ]
    probe = subprocess.run(ffprobe_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if probe.returncode == 0:
        try:
            data = json.loads(probe.stdout)
            duration = float(data.get("format", {}).get("duration", 0))
            width = int(data.get("streams", [{}])[0].get("width", 0))
            height = int(data.get("streams", [{}])[0].get("height", 0))
            return duration, width, height
        except (ValueError, IndexError, KeyError):
            pass
    return 0, 0, 0

def process_video_hls(video_id):
    try:
        video = Video.objects.get(id=video_id)
        video.status = "PROCESSING"
        video.save(update_fields=["status"])

        raw_video_path = video.raw_video.path
        raw_filename = os.path.basename(raw_video_path)
        video_slug = os.path.splitext(raw_filename)[0]

        duration, src_width, src_height = get_video_metadata(raw_video_path)
        video.duration = duration

        if src_width == 0 or src_height == 0:
            raise ValueError("Could not read valid video dimensions from file.")

        hls_output_dir = os.path.join(settings.MEDIA_ROOT, "videos", "hls", video_slug)
        os.makedirs(hls_output_dir, exist_ok=True)

        active_variants = [
            res for res in RESOLUTION_SETTINGS 
            if res["height"] <= src_height or res["name"] == "240p"
        ]
        
        if not active_variants:
            active_variants = [{"name": "src", "width": src_width, "height": src_height, "v_bitrate": "2000k", "a_bitrate": "128k"}]

        ffmpeg_cmd = ["ffmpeg", "-y", "-i", raw_video_path]
        ffmpeg_cmd.extend(["-c:a", "aac", "-keyint_min", "48", "-g", "48", "-sc_threshold", "0"])

        maps = []
        var_stream_map = []

        for i, variant in enumerate(active_variants):
            # Dynamic sharpening matrix to enhance low-res delivery crispness
            scale_filter = (
                f"[0:v]scale=w='min({variant['width']},iw)':h='min({variant['height']},ih)':force_original_aspect_ratio=decrease,"
                f"pad='ceil(iw/2)*2':'ceil(ih/2)*2',"
                f"unsharp=luma_msize_x=5:luma_msize_y=5:luma_amount=0.8:chroma_msize_x=5:chroma_msize_y=5:chroma_amount=0.4[v{i}]"
            )
            
            ffmpeg_cmd.extend(["-filter_complex", scale_filter])
            maps.extend(["-map", f"[v{i}]"])
            
            if variant["height"] >= 2160:
                h264_level = "5.1"
            elif variant["height"] >= 1080:
                h264_level = "4.1"
            else:
                h264_level = "3.1"
            
            ffmpeg_cmd.extend([
                f"-c:v:{i}", "libx264",
                "-preset", "slow",
                f"-profile:v:{i}", "high", 
                f"-level:v:{i}", h264_level,
                f"-b:v:{i}", variant["v_bitrate"],
                f"-maxrate:v:{i}", variant["v_bitrate"],
                f"-bufsize:v:{i}", str(int(variant["v_bitrate"].replace('k','')) * 2) + "k",
            ])
            
            # -------------------------------------------------------------
            # FIX: Audio Normalization Engine Mapping
            # -------------------------------------------------------------
            maps.extend(["-map", "0:a?"])
            ffmpeg_cmd.extend([
                f"-b:a:{i}", variant["a_bitrate"],
                f"-af", "loudnorm=I=-16:TP=-1.5:LRA=11" # <-- Normalizes audio to streaming standard loudness
            ])
            
            var_stream_map.append(f"v:{i},a:{i}")

        ffmpeg_cmd.extend(maps)

        master_playlist_path = os.path.join(hls_output_dir, "master.m3u8")
        ffmpeg_cmd.extend([
            "-f", "hls",
            "-hls_time", "6",
            "-hls_playlist_type", "vod",
            "-master_pl_name", "master.m3u8",
            "-var_stream_map", " ".join(var_stream_map),
            "-hls_segment_filename", os.path.join(hls_output_dir, "%v_segment_%03d.ts"),
            os.path.join(hls_output_dir, "%v_playlist.m3u8")
        ])

        result = subprocess.run(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        if result.returncode == 0:
            video.hls_playlist = Path(os.path.relpath(master_playlist_path, settings.MEDIA_ROOT)).as_posix()
            video.status = "READY"
        else:
            print(result.stderr)
            video.status = "FAILED"

        video.save()

    except Exception as e:
        print("\n========== VIDEO PROCESS ERROR ==========")
        print(str(e))
        print("=========================================\n")
        try:
            failed_video = Video.objects.get(id=video_id)
            failed_video.status = "FAILED"
            failed_video.save(update_fields=["status"])
        except Exception:
            pass


def start_video_processing(video_id):
    """Run video processing in a background thread."""
    thread = threading.Thread(target=process_video_hls, args=(video_id,), daemon=True)
    thread.start()