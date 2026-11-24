from django.conf import settings
from django.conf.urls.static import static
from django.urls import path
from publishing import views
from publishing.media_views import public_media

urlpatterns = [
    path("", views.index),
    path("api/session/", views.session),
    path("api/register/", views.credentials, {"action": "register"}),
    path("api/login/", views.credentials, {"action": "login"}),
    path("api/logout/", views.credentials, {"action": "logout"}),
    path("api/posts/", views.PostList.as_view()),
    path("api/posts/<int:pk>/", views.PostDetail.as_view()),
    path("api/posts/<int:pk>/cancel/", views.cancel),
    path("api/accounts/", views.accounts),
    path("api/assistant/", views.assistant),
    path("api/generate-image/", views.generate_image_view),
    path("media/<path:path>", public_media),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

