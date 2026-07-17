# authentication/urls.py
from django.urls import path
from .views import RegisterView, SecureLoginView, SecureLogoutView, UserProfileView, SecureTokenRefreshView


urlpatterns = [
    path('register/', RegisterView.as_view(), name='auth_register'),
    path('login/', SecureLoginView.as_view(), name='auth_login'),
    path('logout/', SecureLogoutView.as_view(), name='auth_logout'),
    path('me/', UserProfileView.as_view(), name='auth_me'),
    # Swapped target class endpoint here
    path('token/refresh/', SecureTokenRefreshView.as_view(), name='token_refresh'), 
]