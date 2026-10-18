"""Import GA4 revenue/orders into daily metrics (cron-friendly).

Examples: run daily after midnight to refresh the last week, and once a week
with ``--organic`` to refresh the growth report's sessions-per-source table.

    python manage.py sync_google --days 7
    python manage.py sync_google --days 30 --organic
"""
from django.core.management.base import BaseCommand, CommandError

from integrations.services import record_sync

from google_sync import ga4
from google_sync.services import SyncNotConfigured, sync_ga4

#: Traffic is a monthly view by default; a single day of sessions says nothing.
ORGANIC_WINDOW_DAYS = 30


class Command(BaseCommand):
    help = "Pull Google Analytics (GA4) daily revenue and orders into daily metrics."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=None,
            help="How many days back to refresh (default: the last 7, max 365).",
        )
        parser.add_argument(
            "--organic",
            action="store_true",
            help=(
                "Also import GA4 sessions per source for the growth report "
                f"(defaults to the last {ORGANIC_WINDOW_DAYS} days unless --days is set)."
            ),
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

        if not options["organic"]:
            return

        # Imported here so the revenue-only path keeps its small import surface.
        from growth.traffic import DEFAULT_WINDOW_DAYS, sync_organic

        try:
            traffic = sync_organic(days=options["days"] or DEFAULT_WINDOW_DAYS)
        except SyncNotConfigured as exc:
            raise CommandError(str(exc))
        except ga4.GA4Error as exc:
            record_sync("google-analytics", error=str(exc))
            raise CommandError(str(exc))

        record_sync("google-analytics")
        self.stdout.write(self.style.SUCCESS(f"GA4 organic {traffic.start} → {traffic.end}: {traffic.summary()}"))
        if traffic.other_sources:
            self.stdout.write(
                self.style.WARNING("Non-social sources: " + ", ".join(traffic.other_sources[:10]))
            )
