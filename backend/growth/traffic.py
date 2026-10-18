"""Pull GA4 organic traffic into :class:`TrafficSnapshot` rows.

``PostPerformance`` says what was published; this says what arrived. Without it
the report can only rank posts against each other, not against reality — a post
with 40 000 impressions and no sessions is not a win.

Reuses the same Google Analytics integration as the revenue sync (Settings →
API keys), and is idempotent per ``(date, source, medium)``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date as date_type

from django.db import transaction

from google_sync import ga4
from google_sync.services import PROVIDER, SyncNotConfigured, resolve_window
from integrations.services import get_credential_config, get_credential_value

from .models import TrafficSnapshot
from .sources import is_social, platform_for_source

logger = logging.getLogger(__name__)

#: A month is the right default here: single days are too noisy to act on.
DEFAULT_WINDOW_DAYS = 30


@dataclass
class TrafficResult:
    """Outcome of a traffic sync, shaped for the API/CLI response."""

    created: int = 0
    updated: int = 0
    rows: int = 0
    sessions: int = 0
    social_sessions: int = 0
    other_sources: list = field(default_factory=list)
    start: str | None = None
    end: str | None = None

    def as_dict(self) -> dict:
        return {
            "created": self.created,
            "updated": self.updated,
            "rows": self.rows,
            "sessions": self.sessions,
            "social_sessions": self.social_sessions,
            "other_sources": self.other_sources,
            "start": self.start,
            "end": self.end,
        }

    def summary(self) -> str:
        return (
            f"{self.sessions} sessions ({self.social_sessions} from social) "
            f"across {self.rows} report rows — {self.created} created, {self.updated} updated"
        )


def _credentials(credentials_json: str | None, property_id: str | None) -> tuple[str, str]:
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
    return str(credentials_json), str(property_id)


def persist_traffic(rows: list[dict], result: TrafficResult) -> TrafficResult:
    """Upsert report rows; sources that are not one of ours are collected."""
    others: set[str] = set()
    for row in rows:
        result.rows += 1
        result.sessions += row["sessions"]
        platform = platform_for_source(row["source"])
        if platform or is_social(row["medium"]):
            result.social_sessions += row["sessions"]
        else:
            others.add(row["source"])

        raw_date = row["date"]
        day = raw_date if isinstance(raw_date, date_type) else date_type.fromisoformat(str(raw_date))
        with transaction.atomic():
            _, created = TrafficSnapshot.objects.update_or_create(
                date=day,
                source=row["source"],
                medium=row["medium"],
                defaults={
                    "sessions": row["sessions"],
                    "engaged_sessions": row["engaged_sessions"],
                    "users": row["users"],
                    "views": row["views"],
                },
            )
        result.created += int(created)
        result.updated += int(not created)

    result.other_sources = sorted(others, key=str.casefold)
    return result


def sync_organic(
    days: int | None = None,
    credentials_json: str | None = None,
    property_id: str | None = None,
    today=None,
) -> TrafficResult:
    """Pull per-source sessions for the last N days into traffic snapshots.

    Raises ``SyncNotConfigured`` when the integration is unusable and
    ``ga4.GA4Error`` when Google refuses the call.
    """
    credentials_json, property_id = _credentials(credentials_json, property_id)
    start, end = resolve_window(days or DEFAULT_WINDOW_DAYS, today)
    rows = ga4.fetch_traffic_daily(credentials_json, property_id, start, end)
    logger.info("GA4 organic traffic %s → %s returned %d row(s)", start, end, len(rows))
    return persist_traffic(rows, TrafficResult(start=start.isoformat(), end=end.isoformat()))


__all__ = ["DEFAULT_WINDOW_DAYS", "TrafficResult", "persist_traffic", "sync_organic"]
