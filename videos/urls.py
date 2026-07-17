# videos/urls.py
from django.urls import path, include
from rest_framework.routers import SimpleRouter
from .views import VideoUploadView, VideoFeedView, VideoSearchView, VideoViewSet, VideoTrendingView, VideoHistoryViewSet

router = SimpleRouter()
router.register(r'history', VideoHistoryViewSet, basename='history')
router.register(r'', VideoViewSet, basename='video')

urlpatterns = [
    path('upload/', VideoUploadView.as_view(), name='video_upload'),
    path('feed/', VideoFeedView.as_view(), name='video_feed'),
    path('search/', VideoSearchView.as_view(), name='video_search'),
    path('trending/', VideoTrendingView.as_view(), name='video_trending'), # 👈 Add Trending url path
    
    path('', include(router.urls)), # 👈 Includes history and standard routes
]