"""Import GA4 revenue/orders into daily metrics (cron-friendly).

Example: run daily after midnight to refresh the last week.

    python manage.py sync_google --days 7
"""
from django.core.management.base import BaseCommand, CommandError

from integrations.services import record_sync

from google_sync import ga4
from google_sync.services import SyncNotConfigured, sync_ga4


class Command(BaseCommand):
    help = "Pull Google Analytics (GA4) daily revenue and orders into daily metrics."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=None,
            help="How many days back to refresh (default: the last 7, max 365).",
        )

    def handle(self, *args, **options):
        try:
            result = sync_ga4(days=options["days"])
        except SyncNotConfigured as exc:
            raise CommandError(str(exc))
        except ga4.GA4Error as exc:
            record_sync("google-analytics", error=str(exc))
            raise CommandError(str(exc))

        record_sync("google-analytics")
        self.stdout.write(
            self.style.SUCCESS(f"GA4 sync {result.start} → {result.end}: {result.summary()}")
        )
        if result.unmatched:
            self.stdout.write(
                self.style.WARNING("Unmatched campaigns: " + ", ".join(result.unmatched))
            )
