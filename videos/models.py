from django.db import models
from django.contrib.auth import get_user_model
# 👇 Import the PostgreSQL search vectors and indexes
from django.contrib.postgres.search import SearchVectorField
from django.contrib.postgres.indexes import GinIndex

User = get_user_model()

class Video(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending Upload'),
        ('PROCESSING', 'Processing (FFmpeg)'),
        ('READY', 'Ready for Streaming'),
        ('FAILED', 'Processing Failed'),
    ]

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    duration = models.FloatField(default=0)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='videos')
    
    # File paths
    raw_video = models.FileField(upload_to='videos/raw/', help_text="Original uploaded MP4")
    hls_playlist = models.CharField(max_length=500, blank=True, null=True, help_text="Path to .m3u8 file")
    thumbnail = models.ImageField(upload_to='videos/thumbnails/', blank=True, null=True)
    
    # State tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    views_count = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # 👇 Pre-computed search vector holding internal document tokens
    search_vector = SearchVectorField(null=True, blank=True)

    class Meta:
        # Keep your historical video chronologies matching feed defaults
        ordering = ["-created_at"]
        
        # 👇 Add the GIN index targeting the vector token field for microsecond lookup speeds
        indexes = [
            GinIndex(fields=['search_vector'], name='video_search_vector_gin'),
        ]

    def __str__(self):
        return self.title
    
    
class VideoHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='viewing_history')
    video = models.ForeignKey(Video, on_delete=models.CASCADE, related_name='history_logs')
    viewed_at = models.DateTimeField(auto_now=True) # Updates timestamp if rewatched

    class Meta:
        ordering = ['-viewed_at']
        unique_together = ('user', 'video') # Keeps entries unique per video per user

    def __str__(self):
        return f"{self.user.username} watched {self.video.title}"