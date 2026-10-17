"""Sync Google Analytics (GA4) data into DailyMetric rows.

GA4 has no ad cost, so a sync only writes ``revenue`` and ``orders``: it never
touches ``spend``/``ctr`` that came from elsewhere, and it recomputes ``roas``
from whatever spend the row already has. Re-running is idempotent.
"""
import logging
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from integrations.services import get_credential_config, get_credential_value
from results.models import DailyMetric

from . import ga4, mapping

logger = logging.getLogger(__name__)

PROVIDER = "google-analytics"
DEFAULT_WINDOW_DAYS = 7
MAX_WINDOW_DAYS = 365
CENTS = Decimal("0.01")


class SyncNotConfigured(RuntimeError):
    """The integration is missing credentials or a required setting."""


@dataclass
class SyncResult:
    """Outcome of a sync run, shaped for the API/CLI response."""

    created: int = 0
    updated: int = 0
    skipped: int = 0
    rows: int = 0
    unmatched: list = field(default_factory=list)
    start: str | None = None
    end: str | None = None

    def as_dict(self) -> dict:
        return {
            "created": self.created,
            "updated": self.updated,
            "skipped": self.skipped,
            "rows": self.rows,
            "unmatched": self.unmatched,
            "start": self.start,
            "end": self.end,
        }

    def summary(self) -> str:
        return (
            f"{self.created} created, {self.updated} updated, {self.skipped} skipped "
            f"({self.rows} report rows)"
        )


def resolve_window(days: int | None, today=None) -> tuple:
    """Clamp ``days`` into range and return an inclusive ``(start, end)`` window."""
    try:
        count = int(days) if days is not None else DEFAULT_WINDOW_DAYS
    except (TypeError, ValueError):
        count = DEFAULT_WINDOW_DAYS
    count = max(1, min(count, MAX_WINDOW_DAYS))
    end = today or timezone.localdate()
    return end - timedelta(days=count - 1), end


def _money(value) -> Decimal:
    """GA4 sends revenue as a string; normalise to cents, never negative."""
    try:
        amount = Decimal(str(value)).quantize(CENTS, rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0.00")
    return amount if amount > 0 else Decimal("0.00")


def _roas(revenue, spend) -> float:
    try:
        spend = Decimal(str(spend or 0))
        if not spend:
            return 0.0
        return round(float(Decimal(str(revenue or 0)) / spend), 2)
    except (InvalidOperation, TypeError, ValueError):
        return 0.0


def persist_rows(rows: list[dict], result: SyncResult) -> SyncResult:
    """Upsert report rows into DailyMetric; unmapped campaigns are collected."""
    index = mapping.campaign_index()
    unmatched: set = set()

    for row in rows:
        result.rows += 1
        campaign_name = row.get("campaign")
        if mapping.is_ignored(campaign_name):
            result.skipped += 1
            continue
        campaign = index.get(mapping.normalize(campaign_name))
        if campaign is None:
            unmatched.add(str(campaign_name).strip())
            result.skipped += 1
            continue

        revenue = _money(row.get("revenue"))
        orders = int(row.get("orders") or 0)
        with transaction.atomic():
            metric, created = DailyMetric.objects.get_or_create(
                campaign=campaign,
                date=row["date"],
                defaults={
                    "revenue": revenue,
                    "orders": orders,
                    "spend": Decimal("0.00"),
                    "roas": 0.0,
                    "source": DailyMetric.SOURCE_GA4,
                },
            )
            if created:
                result.created += 1
                continue
            # Keep the spend/ctr of the existing row; only refresh GA4's numbers.
            metric.revenue = revenue
            metric.orders = orders
            metric.source = DailyMetric.SOURCE_GA4
            metric.roas = _roas(revenue, metric.spend)
            metric.save(update_fields=["revenue", "orders", "source", "roas"])
            result.updated += 1

    result.unmatched = sorted(unmatched, key=str.casefold)
    return result


def sync_ga4(
    days: int | None = None,
    credentials_json: str | None = None,
    property_id: str | None = None,
    today=None,
) -> SyncResult:
    """Pull GA4 revenue/orders and store them as daily metrics.

    Raises ``SyncNotConfigured`` when the integration is not usable and
    ``ga4.GA4Error`` when the API call fails.
    """
    credentials_json = credentials_json or get_credential_value(PROVIDER)
    property_id = property_id or get_credential_config(PROVIDER).get("property_id")
    if not credentials_json:
        raise SyncNotConfigured(
            "Google Analytics is not configured — add the service-account JSON in "
            "Settings → API keys (or set GOOGLE_ANALYTICS_CREDENTIALS)."
        )
    if not property_id:
        raise SyncNotConfigured(
            "No GA4 property ID configured — add it in Settings → API keys "
            "(or set GOOGLE_ANALYTICS_PROPERTY_ID)."
        )

    start, end = resolve_window(days, today)
    rows = ga4.fetch_campaign_daily(str(credentials_json), str(property_id), start, end)
    logger.info("GA4 sync %s → %s returned %d row(s)", start, end, len(rows))
    return persist_rows(rows, SyncResult(start=start.isoformat(), end=end.isoformat()))
