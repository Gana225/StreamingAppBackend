# videos/serializers.py
import random
import string
import os

from rest_framework import serializers
from .models import Video

class VideoUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Video
        fields = ["id", "title", "description", "raw_video", "thumbnail"]

    def generate_filename(self, username, filename):
        ext = os.path.splitext(filename)[1].lower()

        # 4 random alphanumeric characters
        random_part = ''.join(
            random.choices(string.ascii_uppercase + string.digits, k=4)
        )

        # Unique string
        unique_part = ''.join(
            random.choices(string.ascii_lowercase + string.digits, k=12)
        )

        return f"{username}_{random_part}_{unique_part}{ext}"

    def create(self, validated_data):
        user = self.context["request"].user

        uploaded_file = validated_data["raw_video"]

        uploaded_file.name = self.generate_filename(
            user.username,
            uploaded_file.name
        )

        validated_data["user"] = user

        return super().create(validated_data)


class VideoListSerializer(serializers.ModelSerializer):
    user = serializers.CharField(source='user.username', read_only=True)
    hls_url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    avatar_url = serializers.SerializerMethodField() 

    class Meta:
        model = Video
        fields = [
            'id',
            'title',
            'description',
            'user',
            'avatar_url',
            'thumbnail_url',
            'hls_url',
            'status',
            'views_count',
            'created_at',
            'duration',
        ]

    def get_hls_url(self, obj):
        if obj.status == "READY" and obj.hls_playlist:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(f"/media/{obj.hls_playlist}")
        return None

    def get_thumbnail_url(self, obj):
        if obj.thumbnail:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.thumbnail.url)
        return None
    
    def get_avatar_url(self, obj):
        if obj.user.avatar:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.user.avatar.url)
        return None
    
# Append to the bottom of your videos/serializers.py

class VideoDetailSerializer(VideoListSerializer):
    class Meta(VideoListSerializer.Meta):
        # Explicitly inherits all fields from VideoListSerializer.Meta.fields
        pass