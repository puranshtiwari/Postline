from django.conf import settings
from django.http import Http404
from django.views.decorators.http import require_GET
from django.views.static import serve


@require_GET
def public_media(request, path):
    """Serve only media intended to be fetched by Meta at publish time."""
    if not path.startswith(("post-media/", "generated_images/")):
        raise Http404
    return serve(request, path, document_root=settings.MEDIA_ROOT)
