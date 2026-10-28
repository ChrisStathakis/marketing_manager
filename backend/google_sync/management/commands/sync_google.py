"""Import GA4 revenue/orders and Search Console performance (cron-friendly).

Examples: run daily after midnight to refresh the last week, and once a week
with ``--organic`` to refresh the growth report's sessions-per-source table.

    python manage.py sync_google --days 7
    python manage.py sync_google --days 30 --organic
    python manage.py sync_google --search-console-only
"""
from django.core.management.base import BaseCommand, CommandError

from integrations.services import record_sync

from google_sync import ga4
from google_sync.services import SyncNotConfigured, sync_ga4

#: Traffic is a monthly view by default; a single day of sessions says nothing.
ORGANIC_WINDOW_DAYS = 30


class Command(BaseCommand):
    help = "Pull Google Analytics (GA4) and Search Console data into the growth models."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=None,
            help="How many days back to refresh (default: 7 for GA4, 30 for Search Console).",
        )
        parser.add_argument(
            "--organic",
            action="store_true",
            help=(
                "Also import GA4 sessions per source for the growth report "
                f"(defaults to the last {ORGANIC_WINDOW_DAYS} days unless --days is set)."
            ),
        )
        parser.add_argument(
            "--search-console",
            action="store_true",
            help="Also import Google Search Console totals, pages and queries.",
        )
        parser.add_argument(
            "--search-console-only",
            action="store_true",
            help="Skip GA4 and only import Google Search Console.",
        )

    def handle(self, *args, **options):
        if not options["search_console_only"]:
            try:
                result = sync_ga4(days=options["days"])
            except SyncNotConfigured as exc:
                raise CommandError(str(exc))
            except ga4.GA4Error as exc:
                record_sync("google-analytics", error=str(exc))
                raise CommandError(str(exc))

            record_sync("google-analytics")
            self.stdout.write(
                self.style.SUCCESS(f"GA4 sync {result.start} - {result.end}: {result.summary()}")
            )
            if result.unmatched:
                self.stdout.write(
                    self.style.WARNING("Unmatched campaigns: " + ", ".join(result.unmatched))
                )

            if options["organic"]:
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
                self.stdout.write(
                    self.style.SUCCESS(
                        f"GA4 organic {traffic.start} - {traffic.end}: {traffic.summary()}"
                    )
                )
                if traffic.other_sources:
                    self.stdout.write(
                        self.style.WARNING(
                            "Non-social sources: " + ", ".join(traffic.other_sources[:10])
                        )
                    )

        if options["search_console"] or options["search_console_only"]:
            from google_sync.search_console import SearchConsoleError
            from growth.search_console import PROVIDER, sync_search_console

            try:
                search = sync_search_console(days=options["days"])
            except SyncNotConfigured as exc:
                raise CommandError(str(exc))
            except SearchConsoleError as exc:
                record_sync(PROVIDER, error=str(exc))
                raise CommandError(str(exc))

            record_sync(PROVIDER)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Search Console {search.start} - {search.end}: {search.summary()}"
                )
            )
