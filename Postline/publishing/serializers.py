from django.conf import settings
from django.core.files.storage import default_storage
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from .models import Post, Schedule, SocialAccount


class PostSerializer(serializers.ModelSerializer):
    account = serializers.PrimaryKeyRelatedField(queryset=SocialAccount.objects.none(), allow_null=True, required=False)
    media_file = serializers.FileField(source="media", write_only=True, required=False, allow_null=True)
    generated_media_path = serializers.CharField(write_only=True, required=False, allow_blank=True)
    scheduled_at = serializers.DateTimeField(source="schedule.scheduled_at", allow_null=True, required=False)
    status = serializers.CharField(source="schedule.status", read_only=True)
    failure = serializers.CharField(source="schedule.failure", read_only=True)
    published_at = serializers.DateTimeField(source="schedule.published_at", read_only=True)
    external_id = serializers.CharField(source="schedule.external_id", read_only=True)

    class Meta:
        model = Post
        fields = ("id", "account", "platform", "caption", "hashtags", "media_url", "media_file", "generated_media_path", "ai_assisted",
                  "scheduled_at", "status", "failure", "published_at", "external_id", "updated_at")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["account"].queryset = SocialAccount.objects.filter(user=self.context["request"].user)

    def validate(self, attrs):
        account = attrs.get("account")
        platform = attrs["platform"]
        if account and account.platform != platform:
            raise serializers.ValidationError({"account": "Choose an account for the selected platform."})
        url = attrs.get("media_url", "")
        local_demo_url = settings.DEMO and url.lower().startswith(("http://127.0.0.1", "http://localhost"))
        if url and not url.lower().startswith("https://") and not local_demo_url:
            raise serializers.ValidationError({"media_url": "Enter an HTTPS image URL."})
        uploaded_media = attrs.get("media")
        media = uploaded_media
        generated_path = attrs.pop("generated_media_path", "")
        if generated_path:
            if not generated_path.startswith("generated_images/") or not default_storage.exists(generated_path):
                raise serializers.ValidationError({"generated_media_path": "The generated image is no longer available."})
            if uploaded_media:
                raise serializers.ValidationError({"generated_media_path": "Use either an uploaded or generated image."})
            attrs["media"] = generated_path
            media = generated_path
        if uploaded_media and url:
            raise serializers.ValidationError({"media_file": "Use either an uploaded image or an image URL, not both."})
        if uploaded_media and getattr(uploaded_media, "content_type", "") not in {"image/jpeg", "image/png"}:
            raise serializers.ValidationError({"media_file": "Upload a JPEG or PNG image."})
        scheduled = attrs.get("schedule", {}).get("scheduled_at")
        if scheduled:
            if scheduled <= timezone.now():
                raise serializers.ValidationError({"scheduled_at": "Choose a future time."})
            if not account:
                raise serializers.ValidationError({"account": "Choose a connected account to schedule this post."})
            if platform == "instagram" and not (url or media or getattr(self.instance, "media", None)):
                raise serializers.ValidationError({"media_url": "Instagram requires an image URL or uploaded image."})
            if platform == "facebook" and not any((attrs.get("caption"), attrs.get("hashtags"), url, media)):
                raise serializers.ValidationError("Add a caption, hashtags, or an image.")
            if platform == "instagram" and len("\n\n".join(filter(None, [attrs.get("caption"), attrs.get("hashtags")]))) > 2200:
                raise serializers.ValidationError({"caption": "Instagram captions and hashtags must fit within 2,200 characters."})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        time = validated_data.pop("schedule", {}).get("scheduled_at")
        post = Post.objects.create(user=self.context["request"].user, **validated_data)
        self._set_uploaded_media_url(post)
        Schedule.objects.create(post=post, scheduled_at=time, status="scheduled" if time else "draft")
        return post

    @transaction.atomic
    def update(self, instance, validated_data):
        time = validated_data.pop("schedule", {}).get("scheduled_at")
        # Use a conditional write so a worker claim wins over a concurrent edit.
        updated = Schedule.objects.filter(post=instance, status__in=["draft", "scheduled", "failed", "cancelled"]).update(
            scheduled_at=time, status="scheduled" if time else "draft", failure="", attempted_at=None, external_id=""
        )
        if not updated:
            raise serializers.ValidationError("This post is already publishing or published.")
        post = super().update(instance, validated_data)
        self._set_uploaded_media_url(post)
        post.refresh_from_db()
        return post

    def _set_uploaded_media_url(self, post):
        if not post.media:
            return
        request = self.context["request"]
        base = settings.PUBLIC_MEDIA_BASE_URL
        post.media_url = f"{base}{post.media.url}" if base else request.build_absolute_uri(post.media.url)
        post.save(update_fields=["media_url", "updated_at"])

