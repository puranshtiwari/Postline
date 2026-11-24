import json

from django import forms
from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.forms import UserCreationForm
from django.http import FileResponse, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST
from rest_framework import generics, serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import Post, Schedule, SocialAccount
from .serializers import PostSerializer
from .services import IntegrationError, assist, generate_image, verify_account

User = get_user_model()


class RegistrationForm(UserCreationForm):
    email = forms.EmailField(max_length=254)

    class Meta(UserCreationForm.Meta):
        fields = ("username", "email")


def index(request):
    path = settings.BASE_DIR / "frontend/dist/index.html"
    if not path.is_file():
        return HttpResponse("Build the React frontend using the instructions in README.md.", status=503)
    return FileResponse(path.open("rb"), content_type="text/html")


@ensure_csrf_cookie
@api_view(["GET"])
@permission_classes([AllowAny])
def session(request):
    return Response({
        "user": {"username": request.user.username} if request.user.is_authenticated else None,
        "demo": settings.DEMO,
    })


# DRF exempts its outer view from middleware CSRF. Use a regular Django view
# for these session mutations so anonymous login and registration are protected.
@require_POST
def credentials(request, action):
    if action == "logout":
        logout(request)
        return JsonResponse({"user": None})
    try:
        data = json.loads(request.body)
        if not isinstance(data, dict) or any(not isinstance(value, str) for value in data.values()):
            raise ValueError
    except (TypeError, ValueError):
        return JsonResponse({"detail": "Invalid credentials payload."}, status=400)
    if action == "register":
        form = RegistrationForm(data)
        if not form.is_valid():
            return JsonResponse(form.errors, status=400)
        user = form.save()
    else:
        user = authenticate(request, username=data.get("username", ""), password=data.get("password", ""))
        if user is None:
            return JsonResponse({"detail": "Invalid username or password."}, status=400)
    login(request, user)
    return JsonResponse({"user": {"username": user.username}})


class PostList(generics.ListCreateAPIView):
    serializer_class = PostSerializer

    def get_queryset(self):
        return Post.objects.filter(user=self.request.user).select_related("schedule").order_by("-updated_at")


class PostDetail(generics.RetrieveUpdateAPIView):
    serializer_class = PostSerializer
    http_method_names = ["get", "put", "head", "options"]

    def get_queryset(self):
        return Post.objects.filter(user=self.request.user).select_related("schedule")


@api_view(["POST"])
def cancel(request, pk):
    post = get_object_or_404(Post, user=request.user, pk=pk)
    if not Schedule.objects.filter(post=post, status="scheduled").update(status="cancelled"):
        return Response({"detail": "Only scheduled posts can be cancelled."}, status=409)
    return Response({"status": "cancelled"})


class AccountInput(serializers.Serializer):
    platform = serializers.ChoiceField(choices=SocialAccount.Platform.choices)
    demo = serializers.BooleanField(default=False)
    external_id = serializers.RegexField(r"^\d{1,40}$", required=False)
    token = serializers.CharField(required=False, max_length=4096, trim_whitespace=True, write_only=True)


@api_view(["GET", "POST"])
def accounts(request):
    owned = SocialAccount.objects.filter(user=request.user)
    if request.method == "GET":
        return Response(list(owned.order_by("platform", "name").values("id", "name", "platform", "demo")))
    form = AccountInput(data=request.data)
    form.is_valid(raise_exception=True)
    data = form.validated_data
    platform, demo = data["platform"], data["demo"]
    if demo:
        if not settings.DEMO:
            return Response({"detail": "Demo mode is disabled."}, status=403)
        external_id, name, encrypted = "demo", f"Demo {platform.title()}", ""
    else:
        external_id, token = data.get("external_id"), data.get("token")
        if not external_id or not token:
            return Response({"detail": "Enter the account ID and Page access token."}, status=400)
        try:
            name, encrypted = verify_account(platform, external_id, token)
        except IntegrationError as exc:
            return Response({"detail": str(exc)}, status=400)
    account, _ = SocialAccount.objects.update_or_create(
        user=request.user, platform=platform, demo=demo, external_id=external_id,
        defaults={"name": name, "encrypted_token": encrypted},
    )
    return Response({"id": account.pk, "name": name, "platform": platform, "demo": demo})


class AssistantInput(serializers.Serializer):
    action = serializers.ChoiceField(choices=["caption", "refine", "hashtags", "ideas"])
    topic = serializers.CharField(max_length=5000)
    platform = serializers.ChoiceField(choices=SocialAccount.Platform.choices)


class ImageInput(serializers.Serializer):
    prompt = serializers.CharField(max_length=2000)


@api_view(["POST"])
def assistant(request):
    form = AssistantInput(data=request.data)
    form.is_valid(raise_exception=True)
    try:
        return Response(assist(**form.validated_data))
    except IntegrationError as exc:
        return Response({"detail": str(exc)}, status=502)


@api_view(["POST"])
def generate_image_view(request):
    form = ImageInput(data=request.data)
    form.is_valid(raise_exception=True)
    try:
        name, mime, source = generate_image(form.validated_data["prompt"])
    except IntegrationError as exc:
        return Response({"detail": str(exc)}, status=502)
    path = f"{settings.PUBLIC_MEDIA_BASE_URL}{settings.MEDIA_URL}{name}" if settings.PUBLIC_MEDIA_BASE_URL else request.build_absolute_uri(f"{settings.MEDIA_URL}{name}")
    return Response({"media_url": path, "media_path": name, "mime_type": mime, "source": source})

