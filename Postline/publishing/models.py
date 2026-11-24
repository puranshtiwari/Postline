from django.conf import settings
from django.db import models


class SocialAccount(models.Model):
    class Platform(models.TextChoices):
        FACEBOOK = "facebook", "Facebook"
        INSTAGRAM = "instagram", "Instagram"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    platform = models.CharField(max_length=12, choices=Platform.choices)
    external_id = models.CharField(max_length=40)
    name = models.CharField(max_length=150)
    encrypted_token = models.TextField(blank=True)
    demo = models.BooleanField(default=False)

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=["user", "platform", "external_id", "demo"], name="unique_social_identity"
        )]


class Post(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    account = models.ForeignKey(SocialAccount, null=True, on_delete=models.PROTECT)
    platform = models.CharField(max_length=12, choices=SocialAccount.Platform.choices)
    caption = models.TextField(blank=True, max_length=5000)
    hashtags = models.CharField(blank=True, max_length=500)
    media_url = models.URLField(blank=True, max_length=1000)
    media = models.FileField(upload_to="post-media/", blank=True)
    ai_assisted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class Schedule(models.Model):
    class State(models.TextChoices):
        DRAFT = "draft", "Draft"
        SCHEDULED = "scheduled", "Scheduled"
        PUBLISHING = "publishing", "Publishing"
        PUBLISHED = "published", "Published"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    post = models.OneToOneField(Post, on_delete=models.CASCADE, related_name="schedule")
    status = models.CharField(max_length=12, choices=State.choices, default=State.DRAFT, db_index=True)
    scheduled_at = models.DateTimeField(null=True, db_index=True)
    attempted_at = models.DateTimeField(null=True)
    published_at = models.DateTimeField(null=True)
    failure = models.TextField(blank=True)
    external_id = models.CharField(max_length=150, blank=True)

