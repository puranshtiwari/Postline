from celery import shared_task

from .services import process_due_posts


@shared_task(name="publishing.tasks.scan_due_posts")
def scan_due_posts():
    return process_due_posts()
