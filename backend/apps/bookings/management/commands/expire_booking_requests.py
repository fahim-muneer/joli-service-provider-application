from django.core.management.base import BaseCommand

from apps.bookings.services import expire_stale_requests


class Command(BaseCommand):
    help = "Expire booking offers nobody answered in time (run every few minutes, e.g. from cron)."

    def handle(self, *args, **options):
        count = expire_stale_requests()
        self.stdout.write(f"Expired {count} offer(s).")
