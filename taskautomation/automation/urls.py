from django.urls import path

from .auth_views import (
    login,
    logout,
    session_status,
    linkedin_login,
    linkedin_callback,
)
from .linkedin_views import (
    linkedin_preview,
    linkedin_publish_post,
    linkedin_status,
)

urlpatterns = [
    # Authentication
    path("api/auth/login/", login),
    path("api/auth/logout/", logout),
    path("api/auth/session/", session_status),

    # LinkedIn publishing
    path("api/linkedin/status/", linkedin_status),
    path("api/linkedin/preview/", linkedin_preview),
    path("api/linkedin/publish/", linkedin_publish_post),

    # LinkedIn OAuth
    path("link/linkedin/", linkedin_login),
    path("link/linkedin/callback/", linkedin_callback),
]