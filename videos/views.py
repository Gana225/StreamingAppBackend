import os
from pathlib import Path

from django.conf import settings
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector, TrigramSimilarity
from django.db.models import F, Q
from django.utils.decorators import method_decorator

from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .models import Video, VideoHistory
from .serializers import VideoListSerializer, VideoUploadSerializer, VideoDetailSerializer
from .services import get_video_metadata, start_video_processing


# =====================================================================
# 1. VIDEO UPLOAD ARCHITECTURE VIEW
# =====================================================================
class VideoUploadView(generics.CreateAPIView):
    """
    Handles authenticated video and thumbnail uploads, generating immediate thumbnails, 
    and offloading multi-variant resolution adaptive HLS transcoding into background threads.
    """
    serializer_class = VideoUploadSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        user = self.request.user

        # Save video database record initial state
        video = serializer.save()

        # Handle paths and metadata synchronously before background processing
        video_path = video.raw_video.path
        video_dir = Path(video_path).parent
        media_root = Path(settings.MEDIA_ROOT).resolve()

        # Gather file constraints using your metadata helper
        duration, _, _ = get_video_metadata(video_path)
        video.duration = duration
        video.file_size = os.path.getsize(video_path)

        # Generate Thumbnail synchronously so the UI has an image asset right away
        if not video.thumbnail:
            thumbnail_filename = f"{video.id}.jpg"
            thumbnail_absolute_path = video_dir / thumbnail_filename
            
            import subprocess
            subprocess.run([
                "ffmpeg", "-y", "-i", video_path,
                "-ss", "00:00:02", "-vframes", "1",
                str(thumbnail_absolute_path)
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Match internal FileField relative directory configurations
            video.thumbnail = str(thumbnail_absolute_path.relative_to(media_root))

        # Set operational status to PROCESSING
        video.status = "PROCESSING"
        video.save()

        # 🔥 OFFLOAD TO BACKGROUND THREAD 🔥
        start_video_processing(video.id)


# =====================================================================
# 2. PUBLIC PLUGGABLE LIST & SEARCH FEEDS (READ-ONLY)
# =====================================================================
class VideoFeedView(generics.ListAPIView):
    """
    Returns a collection of successfully processed videos available for public viewing.
    """
    serializer_class = VideoListSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        # Only return fully generated adaptive variants on index streams
        return Video.objects.filter(status="READY").select_related('user')


class VideoSearchView(generics.ListAPIView):
    """
    Advanced Intent-Based Search Engine.
    Combines Weighted Full-Text Search vectors with dynamic Trigram Proximity
    to handle typos, partial word phrases, and structural document intent.
    """
    serializer_class = VideoListSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        query_string = self.request.query_params.get('q', '').strip()
        
        # Optimize query: filter only ready streams and join creator data to avoid N+1
        base_queryset = Video.objects.filter(status="READY").select_related('user')

        if not query_string:
            return base_queryset.order_by('-created_at')

        # 1. Break the query string down into individual search tokens
        words = query_string.split()
        
        # 2. Build a lenient fallback filter matrix (catches partial words & text fragments)
        fallback_filter = Q()
        for word in words:
            fallback_filter |= Q(title__icontains=word) | Q(description__icontains=word)

        # 3. Define the Weighted Vector (Title gets priority 'A', Description gets 'B')
        vector = SearchVector('title', weight='A') + SearchVector('description', weight='B')
        query = SearchQuery(query_string, search_type='websearch')

        # 4. Generate the smart combined queryset
        queryset = base_queryset.annotate(
            # Standard Full Text Search Ranking
            fts_rank=SearchRank(vector, query),
            # Fuzzy Trigram Spelling Proximity Similarity score on the Title
            similarity=TrigramSimilarity('title', query_string)
        ).filter(
            # Match via full text query OR fallback keyword filters
            Q(search_vector=query) | fallback_filter
        ).annotate(
            # Combine the scores into a single dynamic relevance index
            final_relevance=F('fts_rank') + F('similarity')
        ).order_by(
            '-final_relevance', # Most mathematically relevant first
            '-views_count'      # If relevance is tied, popular videos bubble up
        )

        return queryset        


class VideoTrendingView(generics.ListAPIView):
    """
    Returns high-traffic processed videos ordered dynamically by view metrics.
    """
    serializer_class = VideoListSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return Video.objects.filter(status="READY").select_related('user').order_by('-views_count', '-created_at')


# =====================================================================
# 3. UNIFIED ACTION VIEWSETS (ROUTER CONFIGURATIONS)
# =====================================================================
class VideoHistoryViewSet(viewsets.ModelViewSet):
    """
    Dedicated account history viewport manager engine.
    """
    serializer_class = VideoListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Pull the underlying video objects related to the logged-in user
        return Video.objects.filter(
            status="READY",
            history_logs__user=self.request.user
        ).select_related('user').order_by('-history_logs__viewed_at')

    @action(detail=False, methods=['delete'])
    def clear_all(self, request):
        """Endpoint to clear entire watch history: DELETE /api/history/clear_all/"""
        VideoHistory.objects.filter(user=request.user).delete()
        return Response({"status": "History wiped completely"}, status=status.HTTP_200_OK)


class VideoViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Core watch page engine managing distinct single item detail reads,
    delayed client intent tracking, and instant target logging hooks.
    """
    queryset = Video.objects.filter(status="READY").select_related('user')
    permission_classes = [AllowAny]

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return VideoDetailSerializer
        return VideoListSerializer

    @action(detail=True, methods=['post'], permission_classes=[AllowAny])
    def view(self, request, pk=None):
        """
        Delayed Intent Target Counter (Fires after verification delay threshold).
        POST /api/videos/<id>/view/
        """
        video = self.get_object()
        
        # Atomically increment total system views via direct DB expressions
        Video.objects.filter(pk=video.pk).update(views_count=F('views_count') + 1)
        
        # Log fallback context window matching older behaviors if requested
        if request.user.is_authenticated:
            VideoHistory.objects.update_or_create(
                user=request.user,
                video=video
            )
        
        video.refresh_from_db()
        return Response({"status": "metric updated", "views_count": video.views_count}, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def log_history(self, request, pk=None):
        """
        Natively maps a video to a user's history log instantly upon click.
        POST /api/videos/<id>/log_history/
        """
        video = self.get_object()
        
        # Instantly write or update the history timestamp
        VideoHistory.objects.update_or_create(
            user=request.user,
            video=video
        )
        
        return Response({"status": "History logged instantly"}, status=status.HTTP_200_OK)