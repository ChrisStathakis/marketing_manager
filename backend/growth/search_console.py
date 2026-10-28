"""Sync and shape Google Search Console data for the growth report.

Search Console has no campaign/UTM dimension. A campaign is therefore joined
to search data through the canonical paths of the pages its content links to.
That is useful for "did the pages we promoted get more search visibility?", but
it is not causal attribution — GA4 remains the UTM source of truth.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import date as date_type
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from content.models import ContentItem
from google_sync import search_console as gsc
from google_sync.services import SyncNotConfigured
from integrations.services import credential_status, get_credential_config, get_credential_value

from .models import SearchConsoleSnapshot

logger = logging.getLogger(__name__)

PROVIDER = "google-search-console"
DEFAULT_WINDOW_DAYS = 30
MAX_WINDOW_DAYS = 365


@dataclass
class SearchConsoleResult:
    created: int = 0
    updated: int = 0
    rows: int = 0
    pages: int = 0
    queries: int = 0
    clicks: int = 0
    impressions: int = 0
    start: str | None = None
    end: str | None = None
    site_url: str = ""

    def as_dict(self) -> dict:
        return {
            "created": self.created,
            "updated": self.updated,
            "skipped": 0,
            "unmatched": [],
            "rows": self.rows,
            "pages": self.pages,
            "queries": self.queries,
            "clicks": self.clicks,
            "impressions": self.impressions,
            "start": self.start,
            "end": self.end,
            "site_url": self.site_url,
        }

    def summary(self) -> str:
        return (
            f"{self.clicks} clicks, {self.impressions} impressions across "
            f"{self.pages} pages and {self.queries} queries — "
            f"{self.created} created, {self.updated} updated"
        )


def _credentials(
    credentials_json: str | None,
    site_url: str | None,
) -> tuple[str, str]:
    credentials_json = credentials_json or get_credential_value(PROVIDER)
    site_url = site_url or get_credential_config(PROVIDER).get("site_url")
    if not credentials_json:
        raise SyncNotConfigured(
            "Google Search Console is not configured — add the service-account JSON "
            "in Settings → API keys (or set GOOGLE_SEARCH_CONSOLE_CREDENTIALS)."
        )
    if not site_url:
        raise SyncNotConfigured(
            "No Search Console property configured — add the exact property in "
            "Settings → API keys (or set GOOGLE_SEARCH_CONSOLE_SITE_URL)."
        )
    return str(credentials_json), str(site_url)


def resolve_window(
    days: int | None,
    campaign=None,
    today: date_type | None = None,
) -> tuple[date_type, date_type]:
    """Inclusive window for the report.

    ``campaign`` does not change the dates: the report's day selector stays the
    same whether you are looking at one campaign or all of them. A campaign
    only filters Search Console rows through its linked page paths.
    """
    day = today or timezone.localdate()
    try:
        count = int(days) if days is not None else DEFAULT_WINDOW_DAYS
    except (TypeError, ValueError):
        count = DEFAULT_WINDOW_DAYS
    count = max(1, min(count, MAX_WINDOW_DAYS))
    return day - timedelta(days=count - 1), day


def previous_window(start: date_type, end: date_type) -> tuple[date_type, date_type]:
    length = max(1, (end - start).days + 1)
    previous_end = start - timedelta(days=1)
    return previous_end - timedelta(days=length - 1), previous_end


def campaign_window(campaign, today: date_type | None = None) -> tuple[date_type, date_type]:
    """The campaign's own window, clipped to today for future/ongoing runs.

    The site-wide Search Console summary follows the report's day selector, but
    the campaign section (and its KPI actuals) should cover the campaign itself.
    """
    day = today or timezone.localdate()
    start = getattr(campaign, "start_date", None) or day - timedelta(days=DEFAULT_WINDOW_DAYS - 1)
    end = getattr(campaign, "end_date", None) or day
    return start, min(end, day)


def persist_rows(
    rows: list[dict],
    site_url: str,
    result: SearchConsoleResult,
) -> SearchConsoleResult:
    pages: set[str] = set()
    queries: set[str] = set()
    for row in rows:
        result.rows += 1
        if row["scope"] == "total":
            result.clicks += int(row.get("clicks") or 0)
            result.impressions += int(row.get("impressions") or 0)
        elif row["scope"] == "page":
            pages.add(row.get("page_path") or "")
        elif row["scope"] == "query":
            queries.add(row.get("query") or "")

        with transaction.atomic():
            _, created = SearchConsoleSnapshot.objects.update_or_create(
                date=row["date"],
                site_url=site_url[:255],
                scope=row["scope"],
                page_path=(row.get("page_path") or "")[:1000],
                query=(row.get("query") or "")[:500],
                defaults={
                    "page_url": (row.get("page_url") or "")[:2000],
                    "clicks": int(row.get("clicks") or 0),
                    "impressions": int(row.get("impressions") or 0),
                    "ctr": float(row.get("ctr") or 0),
                    "position": float(row.get("position") or 0),
                },
            )
        result.created += int(created)
        result.updated += int(not created)

    result.pages = len(pages)
    result.queries = len(queries)
    return result


def sync_search_console(
    days: int | None = None,
    credentials_json: str | None = None,
    site_url: str | None = None,
    today: date_type | None = None,
    timeout: int = gsc.DEFAULT_TIMEOUT,
) -> SearchConsoleResult:
    """Fetch totals, pages and queries for the last N days (idempotent)."""
    credentials_json, site_url = _credentials(credentials_json, site_url)
    start, end = resolve_window(days, today=today)
    rows = gsc.fetch_snapshot(credentials_json, site_url, start, end, timeout=timeout)
    logger.info("Search Console sync %s → %s returned %d row(s)", start, end, len(rows))
    return persist_rows(
        rows,
        site_url,
        SearchConsoleResult(start=start.isoformat(), end=end.isoformat(), site_url=site_url),
    )


def campaign_page_paths(campaign) -> list[str]:
    """Canonical paths linked by the campaign, in stable order."""
    paths = {
        gsc.normalize_page_path(link)
        for link in ContentItem.objects.filter(campaign=campaign)
        .exclude(link="")
        .values_list("link", flat=True)
    }
    if not paths and getattr(campaign, "landing_path", ""):
        paths.add(gsc.normalize_page_path(campaign.landing_path))
    return sorted(paths)


def _rows_totals(rows) -> dict:
    clicks = sum(int(row.clicks or 0) for row in rows)
    impressions = sum(int(row.impressions or 0) for row in rows)
    weighted_position = sum(float(row.position or 0) * int(row.impressions or 0) for row in rows)
    return {
        "clicks": clicks,
        "impressions": impressions,
        "ctr": round(clicks / impressions, 4) if impressions else 0.0,
        "position": round(weighted_position / impressions, 2) if impressions else 0.0,
    }


def _group_rows(rows, key: str) -> list[dict]:
    groups: dict[str, list] = defaultdict(list)
    for row in rows:
        value = getattr(row, key, "") or ""
        if value:
            groups[value].append(row)
    result = []
    for value, group in groups.items():
        totals = _rows_totals(group)
        result.append(
            {
                key: value,
                **totals,
                "page_url": group[0].page_url if key == "page_path" else "",
            }
        )
    return sorted(result, key=lambda item: (-item["clicks"], -item["impressions"], item[key]))[:20]


def build_report(
    *,
    campaign=None,
    days: int | None = None,
    today: date_type | None = None,
) -> dict:
    """Read stored snapshots only; never calls Google."""
    start, end = resolve_window(days, campaign=campaign, today=today)
    previous_start, previous_end = previous_window(start, end)
    status = credential_status(PROVIDER)
    site_url = get_credential_config(PROVIDER).get("site_url") or ""
    configured = bool(status.get("configured"))
    base = SearchConsoleSnapshot.objects.all()
    if site_url:
        base = base.filter(site_url=site_url)

    current = base.filter(date__gte=start, date__lte=end)
    previous = base.filter(date__gte=previous_start, date__lte=previous_end)
    total_rows = list(current.filter(scope="total"))
    previous_total_rows = list(previous.filter(scope="total"))
    page_rows = list(current.filter(scope="page"))
    query_rows = list(current.filter(scope="query"))

    page_paths = campaign_page_paths(campaign) if campaign is not None else []
    page_path_set = set(page_paths)
    campaign_start = campaign_end = None
    if campaign is not None:
        campaign_start, campaign_end = campaign_window(campaign, today=today)
        campaign_page_rows = list(
            base.filter(
                scope="page",
                date__gte=campaign_start,
                date__lte=campaign_end,
            )
        )
        campaign_rows = [row for row in campaign_page_rows if row.page_path in page_path_set]
    else:
        campaign_rows = []
    campaign_totals = _rows_totals(campaign_rows)
    data_through = current.order_by("-date").values_list("date", flat=True).first()

    warning = ""
    if campaign is not None and page_paths == ["/"]:
        warning = (
            "All campaign links point to the homepage, so Search Console can only show "
            "homepage organic search. Add a landing path to the campaign/playbook for "
            "page-level assisted search."
        )
    elif campaign is not None and not campaign_rows:
        warning = "No Search Console rows match the pages linked by this campaign yet."

    return {
        "window": {"start": start, "end": end},
        "previous_window": {"start": previous_start, "end": previous_end},
        "totals": _rows_totals(total_rows),
        "previous_totals": _rows_totals(previous_total_rows),
        "by_page": _group_rows(page_rows, "page_path"),
        "by_query": _group_rows(query_rows, "query"),
        "campaign": {
            "window": {"start": campaign_start, "end": campaign_end},
            "pages": page_paths,
            "totals": campaign_totals,
            "by_page": _group_rows(campaign_rows, "page_path"),
            "matched": bool(campaign_rows),
            "warning": warning,
        }
        if campaign is not None
        else None,
        "data_through": data_through,
        "data_lag_days": 2,
        "configured": configured,
        "site_url": site_url,
        "last_synced_at": status.get("last_synced_at"),
    }
