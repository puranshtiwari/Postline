import base64
import re
from uuid import uuid4
from datetime import timedelta

import requests
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import close_old_connections
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.utils import timezone

from .models import Schedule


class IntegrationError(Exception):
    pass


def process_due_posts(limit=100):
    """Claim and publish due schedules, returning one result per claimed post."""
    close_old_connections()
    now = timezone.now()
    Schedule.objects.filter(
        status="publishing", attempted_at__lt=now - timedelta(minutes=10)
    ).update(
        status="failed",
        failure="The publish attempt was interrupted. Check the destination before rescheduling.",
    )
    due_ids = list(
        Schedule.objects.filter(status="scheduled", scheduled_at__lte=now)
        .order_by("scheduled_at")
        .values_list("pk", flat=True)[:limit]
    )
    results = []
    for schedule_id in due_ids:
        claimed_at = timezone.now()
        claimed = Schedule.objects.filter(
            pk=schedule_id, status="scheduled", scheduled_at__lte=claimed_at
        ).update(status="publishing", attempted_at=claimed_at)
        if not claimed:
            continue
        schedule = Schedule.objects.select_related("post__account").get(pk=schedule_id)
        try:
            external_id = publish(schedule.post)
        except IntegrationError as exc:
            result = {"status": "failed", "failure": str(exc)}
        except Exception:
            result = {
                "status": "failed",
                "failure": "An unexpected error interrupted publishing. Check the destination before rescheduling.",
            }
        else:
            result = {
                "status": "published",
                "external_id": external_id,
                "published_at": timezone.now(),
            }
        Schedule.objects.filter(pk=schedule_id, status="publishing").update(**result)
        results.append({"post_id": schedule.post_id, **result})
    close_old_connections()
    return results


def _request(method, url, provider, **params):
    try:
        response = requests.request(method, url, timeout=(5, 20), allow_redirects=False, **params)
    except requests.RequestException as exc:
        raise IntegrationError(f"{provider} request could not be completed. Check the provider before retrying publishing.") from exc
    if not response.ok or response.is_redirect:
        raise IntegrationError(f"{provider} returned HTTP {response.status_code}. Check account permissions and input.")
    try:
        return response.json()
    except ValueError as exc:
        raise IntegrationError(f"{provider} returned an unreadable response.") from exc


def generate_cloudflare_image(prompt):
    if not settings.CLOUDFLARE_ACCOUNT_ID or not settings.CLOUDFLARE_API_TOKEN:
        return None
    url = f"https://api.cloudflare.com/client/v4/accounts/{settings.CLOUDFLARE_ACCOUNT_ID}/ai/run/{settings.CLOUDFLARE_IMAGE_MODEL}"
    try:
        response = requests.post(
            url,
            headers={"Authorization": f"Bearer {settings.CLOUDFLARE_API_TOKEN}"},
            json={"prompt": prompt, "steps": 4},
            timeout=(5, 90),
        )
    except requests.RequestException as exc:
        raise IntegrationError("Cloudflare image generation could not be completed.") from exc
    try:
        payload = response.json()
    except ValueError as exc:
        raise IntegrationError("Cloudflare returned an unreadable image-generation response.") from exc
    if not response.ok or not payload.get("success", True):
        errors = "; ".join(item.get("message", "Unknown error") for item in payload.get("errors", []))
        raise IntegrationError(f"Cloudflare image generation failed: {errors or response.reason}")
    encoded = payload.get("result", {}).get("image") or payload.get("image")
    if not encoded:
        raise IntegrationError("Cloudflare did not return an image.")
    return base64.b64decode(encoded)


def generate_image(prompt):
    cloudflare_content = generate_cloudflare_image(prompt)
    if cloudflare_content:
        filename = f"generated-{uuid4().hex}.jpg"
        name = default_storage.save(f"generated_images/{filename}", ContentFile(cloudflare_content))
        return name, "image/jpeg", "cloudflare"
    if not settings.GEMINI_API_KEY:
        if not settings.DEMO:
            raise IntegrationError("Configure GEMINI_API_KEY to generate images.")
        svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1024"><rect width="100%" height="100%" fill="#172554"/><text x="50%" y="48%" fill="white" font-size="42" text-anchor="middle" font-family="Arial">Demo image</text><text x="50%" y="54%" fill="#bfdbfe" font-size="24" text-anchor="middle" font-family="Arial">{prompt[:80]}</text></svg>'''
        content = svg.encode()
        name = default_storage.save(f"generated_images/generated-{uuid4().hex}.svg", ContentFile(content))
        return name, "image/svg+xml", "demo"
    model = settings.GEMINI_IMAGE_MODEL
    if not re.fullmatch(r"[\w.-]+", model):
        raise IntegrationError("Configure a valid GEMINI_IMAGE_MODEL.")
    result = _request(
        "POST",
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        "Gemini",
        headers={"x-goog-api-key": settings.GEMINI_API_KEY},
        json={"contents": [{"parts": [{"text": f"Generate a high-quality square social media image. Prompt: {prompt}"}]}],
              "generationConfig": {"responseModalities": ["IMAGE"]}},
    )
    parts = (result.get("candidates") or [{}])[0].get("content", {}).get("parts", [])
    for part in parts:
        image = part.get("inlineData") or part.get("inline_data")
        if image and image.get("data"):
            mime = image.get("mimeType") or image.get("mime_type") or "image/png"
            extension = "jpg" if mime == "image/jpeg" else "png"
            content = base64.b64decode(image["data"])
            filename = f"generated-{uuid4().hex}.{extension}"
            name = default_storage.save(f"generated_images/{filename}", ContentFile(content))
            return name, mime, "gemini"
    raise IntegrationError("Gemini did not return an image. Try a different prompt.")


def _cipher():
    try:
        return Fernet(settings.TOKEN_KEY.encode())
    except ValueError as exc:
        raise IntegrationError("Configure a valid TOKEN_KEY on the server.") from exc


def graph(method, path, token, **params):
    version = settings.META_GRAPH_VERSION
    if not re.fullmatch(r"v\d+\.\d+", version):
        raise IntegrationError("Configure a valid Meta Graph API version.")
    return _request(method, f"https://graph.facebook.com/{version}/{path}", "Meta",
                    headers={"Authorization": f"Bearer {token}"}, **params)


def verify_account(platform, external_id, token):
    cipher = _cipher()
    fields = "id,name" if platform == "facebook" else "id,instagram_business_account"
    page = graph("GET", "me", token, params={"fields": fields})
    if platform == "facebook" and page.get("id") == external_id:
        name = page.get("name") or "Facebook Page"
    elif platform == "instagram" and (page.get("instagram_business_account") or {}).get("id") == external_id:
        profile = graph("GET", external_id, token, params={"fields": "id,username"})
        name = profile.get("username") or "Instagram"
    else:
        raise IntegrationError("The Page token does not match the selected Facebook Page or linked Instagram account.")
    return name[:150], cipher.encrypt(token.encode()).decode()


def publish(post):
    account = post.account
    if not account:
        raise IntegrationError("Choose a connected account before publishing.")
    if account.demo:
        if not settings.DEMO:
            raise IntegrationError("Demo publishing is disabled.")
        return f"demo-{post.pk}"
    try:
        token = _cipher().decrypt(account.encrypted_token.encode()).decode()
    except InvalidToken as exc:
        raise IntegrationError("Reconnect this account to refresh its stored token.") from exc
    caption = "\n\n".join(filter(None, [post.caption, post.hashtags]))
    if account.platform == "instagram":
        container = graph("POST", f"{account.external_id}/media", token,
                          data={"image_url": post.media_url, "caption": caption})
        if not container.get("id"):
            raise IntegrationError("Instagram did not return a media container ID.")
        result = graph("POST", f"{account.external_id}/media_publish", token,
                       data={"creation_id": container["id"]})
    elif post.media_url:
        result = graph("POST", f"{account.external_id}/photos", token,
                       data={"url": post.media_url, "caption": caption})
    else:
        result = graph("POST", f"{account.external_id}/feed", token, data={"message": caption})
    external_id = result.get("post_id") or result.get("id")
    if not external_id:
        raise IntegrationError("Meta did not return a published post ID. Check the destination before retrying.")
    return str(external_id)


def assist(action, topic, platform):
    instructions = {
        "caption": "Write one ready-to-edit social caption.",
        "refine": "Rewrite the supplied caption for clarity and engagement. Preserve its facts.",
        "hashtags": "Return up to eight relevant hashtags on one line, separated by spaces.",
        "ideas": "Give three short social post ideas, one per line.",
    }
    if not settings.GEMINI_API_KEY:
        if not settings.DEMO:
            raise IntegrationError("Configure GEMINI_API_KEY to use the assistant.")
        templates = {
            "caption": f"Let's talk about {topic}. What do you want to know most? Share your thoughts below.",
            "refine": f"{topic.rstrip('.')}. What's your take? Tell us in the comments.",
            "hashtags": "#" + ("".join(re.findall(r"[A-Za-z0-9]+", topic.title()))[:45] or "Topic") + " #Community #Creator",
            "ideas": f"1. Share a behind-the-scenes look at {topic}.\n2. Answer one common question.\n3. Ask your audience to vote.",
        }
        return {"text": templates[action], "source": "demo"}
    if not re.fullmatch(r"[\w.-]+", settings.GEMINI_MODEL):
        raise IntegrationError("Configure a valid GEMINI_MODEL.")
    result = _request("POST",
        f"https://generativelanguage.googleapis.com/v1beta/models/{settings.GEMINI_MODEL}:generateContent",
        "Gemini", headers={"x-goog-api-key": settings.GEMINI_API_KEY},
        json={"contents": [{"parts": [{"text": f"{instructions[action]} Platform: {platform}. Return only the requested content.\n\nUser input:\n{topic}"}]}]})
    candidates = result.get("candidates") or []
    parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
    answer = "\n".join(part.get("text", "") for part in parts if not part.get("thought")).strip()
    if not answer:
        raise IntegrationError("Gemini did not return text. Try revising your prompt.")
    return {"text": answer, "source": "gemini"}

