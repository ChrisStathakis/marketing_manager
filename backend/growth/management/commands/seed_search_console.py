"""Seed deterministic Search Console snapshots for local demos.

This does **not** call Google. It writes plausible total/page/query rows so the
growth studio's assisted-search section can be explored without credentials.
Rows are keyed like a real sync, so re-running updates rather than duplicates.
"""
from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from growth.models import SearchConsoleSnapshot

DEFAULT_SITE = "sc-domain:catchandstats.com"

PAGE_SHARES = (
    ("/", 0.38, 4.8),
    ("/team-advanced-stats", 0.27, 3.4),
    ("/players", 0.16, 5.6),
    ("/euroleague", 0.12, 6.2),
)

QUERY_SHARES = (
    ("euroleague standings", 0.22, 2.8),
    ("euroleague top 8", 0.18, 3.1),
    ("basketball advanced stats", 0.14, 5.4),
    ("catch and stats", 0.11, 1.6),
    ("euroleague round 7", 0.08, 3.9),
    ("euroleague net rating", 0.07, 4.4),
)


class Command(BaseCommand):
    help = "Create dummy Google Search Console snapshots (local demos only)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=30,
            help="How many trailing days to seed (default: 30, max 365).",
        )
        parser.add_argument(
            "--site-url",
            default=DEFAULT_SITE,
            help=f"Search Console property string (default: {DEFAULT_SITE}).",
        )

    def handle(self, *args, **options):
        days = max(1, min(int(options["days"]), 365))
        site_url = options["site_url"]
        today = timezone.localdate()
        # Demo data deliberately includes today so a campaign that just started
        # still has something to show; a real sync leaves Google's 2-3 day lag.
        last_day = today
        created = updated = 0

        for offset in range(days):
            day = last_day - timedelta(days=offset)
            wave = 1 + (day.weekday() / 12)
            total_clicks = max(20, int(118 * wave) + (offset % 5) * 3)
            total_impressions = total_clicks * (17 + offset % 4)
            rows = [
                {
                    "scope": "total",
                    "page_url": "",
                    "page_path": "",
                    "query": "",
                    "clicks": total_clicks,
                    "impressions": total_impressions,
                    "position": 4.6,
                }
            ]
            for path, share, position in PAGE_SHARES:
                clicks = max(1, int(total_clicks * share))
                rows.append(
                    {
                        "scope": "page",
                        "page_url": f"https://www.catchandstats.com{path}",
                        "page_path": path,
                        "query": "",
                        "clicks": clicks,
                        "impressions": max(clicks, int(total_impressions * share)),
                        "position": position,
                    }
                )
            for query, share, position in QUERY_SHARES:
                clicks = max(0, int(total_clicks * share))
                rows.append(
                    {
                        "scope": "query",
                        "page_url": "",
                        "page_path": "",
                        "query": query,
                        "clicks": clicks,
                        "impressions": max(clicks, int(total_impressions * share)),
                        "position": position,
                    }
                )

            for row in rows:
                clicks = row["clicks"]
                impressions = row["impressions"]
                _, was_created = SearchConsoleSnapshot.objects.update_or_create(
                    date=day,
                    site_url=site_url,
                    scope=row["scope"],
                    page_path=row["page_path"],
                    query=row["query"],
                    defaults={
                        "page_url": row["page_url"],
                        "clicks": clicks,
                        "impressions": impressions,
                        "ctr": round(clicks / impressions, 4) if impressions else 0,
                        "position": row["position"],
                    },
                )
                created += int(was_created)
                updated += int(not was_created)

        self.stdout.write(
            self.style.SUCCESS(
                f"Search Console demo data ready for {site_url}: "
                f"{created} created, {updated} updated ({days} days)."
            )
        )
