# streaming/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from .views import dns_verification

urlpatterns = [
    path('', dns_verification, name='dns-verify'),
    path('admin/', admin.site.path if hasattr(admin.site, 'path') else admin.site.urls),
    path('api/auth/', include('authentication.urls')),
    path('api/videos/', include('videos.urls')),
]

# if settings.DEBUG:
#     urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)