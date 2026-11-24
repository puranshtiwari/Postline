import time

from django.core.management.base import BaseCommand
from django.db import OperationalError, close_old_connections

from publishing.services import process_due_posts


class Command(BaseCommand):
    help = "Publish due posts. Use --once for a single scan."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true")
        parser.add_argument("--interval", type=int, default=5)

    def handle(self, *args, **options):
        try:
            while True:
                close_old_connections()
                try:
                    self.scan()
                except OperationalError as exc:
                    if options["once"] or "locked" not in str(exc).lower():
                        raise
                    self.stderr.write("Database busy. Retrying on the next scan.")
                if options["once"]:
                    return
                time.sleep(max(1, options["interval"]))
        except KeyboardInterrupt:
            return

    def scan(self):
        for result in process_due_posts():
            self.stdout.write(f"Post #{result['post_id']}: {result['status']}")

