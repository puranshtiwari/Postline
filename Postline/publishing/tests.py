from datetime import timedelta
import base64
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.files.storage import default_storage

from .models import Post, Schedule, SocialAccount
from .services import IntegrationError, generate_image, process_due_posts
from .tasks import scan_due_posts


@override_settings(DEMO=True)
class SchedulingTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="demo-user", password="password")
        self.account = SocialAccount.objects.create(
            user=self.user, platform="facebook", external_id="demo", name="Demo Facebook", demo=True
        )

    def make_post(self, status="scheduled", scheduled_at=None, account=None):
        post = Post.objects.create(
            user=self.user, account=account or self.account, platform="facebook", caption="Demo post"
        )
        Schedule.objects.create(
            post=post, status=status,
            scheduled_at=scheduled_at or timezone.now() - timedelta(seconds=1),
        )
        return post

    def test_due_demo_post_is_published_once(self):
        post = self.make_post()

        first = process_due_posts()
        second = scan_due_posts.run()

        self.assertEqual([result["post_id"] for result in first], [post.pk])
        self.assertEqual(first[0]["status"], "published")
        self.assertEqual(second, [])
        schedule = Schedule.objects.get(post=post)
        self.assertEqual(schedule.status, "published")
        self.assertEqual(schedule.external_id, f"demo-{post.pk}")

    def test_future_and_cancelled_posts_are_skipped(self):
        future = self.make_post(scheduled_at=timezone.now() + timedelta(minutes=5))
        cancelled = self.make_post(status="cancelled")

        self.assertEqual(process_due_posts(), [])
        self.assertEqual(Schedule.objects.get(post=future).status, "scheduled")
        self.assertEqual(Schedule.objects.get(post=cancelled).status, "cancelled")

    @patch("publishing.services.publish", side_effect=IntegrationError("Meta rejected the post."))
    def test_publishing_failure_is_recorded(self, publish_mock):
        post = self.make_post()

        results = process_due_posts()

        self.assertEqual(results[0]["status"], "failed")
        self.assertEqual(results[0]["failure"], "Meta rejected the post.")
        self.assertEqual(Schedule.objects.get(post=post).status, "failed")
        publish_mock.assert_called_once()

    @override_settings(
        CLOUDFLARE_ACCOUNT_ID="test-account",
        CLOUDFLARE_API_TOKEN="test-token",
        CLOUDFLARE_IMAGE_MODEL="@cf/black-forest-labs/flux-1-schnell",
    )
    @patch("publishing.services.requests.post")
    def test_cloudflare_image_is_decoded_and_saved_locally(self, post_mock):
        post_mock.return_value.ok = True
        post_mock.return_value.json.return_value = {
            "success": True,
            "result": {"image": base64.b64encode(b"mock-jpeg-bytes").decode()},
        }

        name, mime, source = generate_image("A demo product photo")

        self.assertTrue(name.startswith("generated_images/"))
        self.assertEqual(mime, "image/jpeg")
        self.assertEqual(source, "cloudflare")
        self.assertTrue(default_storage.exists(name))
        post_mock.assert_called_once()
