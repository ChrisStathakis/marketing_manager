"""Aggregations shared by the growth report and the recommendation rules.

Everything here takes plain lists of model instances and returns plain dicts:
no database access, no request objects. That keeps the rules in ``insights.py``
testable without a fixture factory, and the API view free to attach serialized
posts afterwards.
"""

from __future__ import annotations

from .sources import platform_for_source


def group_stats(rows: list) -> dict:
    """Impressions/engagements/clicks rolled up, with both rates."""
    impressions = sum(row.impressions for row in rows)
    engagements = sum(row.engagements for row in rows)
    clicks = sum(row.clicks for row in rows)
    return {
        "posts": len(rows),
        "impressions": impressions,
        "engagements": engagements,
        "comments": sum(row.comments for row in rows),
        "clicks": clicks,
        "engagement_rate": round(engagements / impressions, 4) if impressions else None,
        "click_rate": round(clicks / impressions, 4) if impressions else None,
    }


def group_by(rows: list, attr: str, labels: dict | None = None, drop_empty: bool = True) -> list[dict]:
    """Group posts by one attribute, best click rate first.

    ``attr`` is a model field name (``platform``, ``kind``, ``metric_key``).
    """
    buckets: dict[str, list] = {}
    for row in rows:
        key = str(getattr(row, attr, "") or "")
        if drop_empty and not key:
            continue
        buckets.setdefault(key, []).append(row)

    grouped = []
    for key, bucket in buckets.items():
        grouped.append(
            {
                "key": key,
                "label": (labels or {}).get(key, key or "Unlabelled"),
                "stats": group_stats(bucket),
            }
        )
    grouped.sort(
        key=lambda entry: (
            entry["stats"]["click_rate"] or 0.0,
            entry["stats"]["engagement_rate"] or 0.0,
            entry["stats"]["impressions"],
        ),
        reverse=True,
    )
    return grouped


def platform_trend(current: list, previous: list, labels: dict | None = None) -> list[dict]:
    """Per-platform change between two equally long windows."""
    now = {entry["key"]: entry for entry in group_by(current, "platform", labels)}
    before = {entry["key"]: entry for entry in group_by(previous, "platform", labels)}

    trend = []
    for key in sorted(set(now) | set(before)):
        current_stats = now.get(key, {}).get("stats") or group_stats([])
        previous_stats = before.get(key, {}).get("stats") or group_stats([])
        current_rate = current_stats["click_rate"]
        previous_rate = previous_stats["click_rate"]
        delta = (
            round(current_rate - previous_rate, 4)
            if current_rate is not None and previous_rate is not None
            else None
        )
        trend.append(
            {
                "platform": key,
                "label": (labels or {}).get(key, key),
                "clicks": current_stats["clicks"],
                "previous_clicks": previous_stats["clicks"],
                "click_rate": current_rate,
                "previous_click_rate": previous_rate,
                "delta_click_rate": delta,
                "posts": current_stats["posts"],
                "previous_posts": previous_stats["posts"],
                "direction": "flat" if not delta else ("up" if delta > 0 else "down"),
            }
        )
    trend.sort(key=lambda entry: entry["clicks"], reverse=True)
    return trend


def flatten(entries: list[dict], key_name: str) -> list[dict]:
    """``group_by`` output with the stats merged up: one flat row per group."""
    return [{key_name: entry["key"], "label": entry["label"], **entry["stats"]} for entry in entries]


def traffic_summary(snapshots: list, labels: dict | None = None) -> dict:
    """Roll GA4 snapshots up by platform and by source."""
    totals = {"sessions": 0, "social_sessions": 0, "engaged_sessions": 0, "users": 0, "views": 0}
    by_platform: dict[str, dict] = {}
    by_source: dict[tuple, dict] = {}

    for row in snapshots:
        totals["sessions"] += row.sessions
        totals["engaged_sessions"] += row.engaged_sessions
        totals["users"] += row.users
        totals["views"] += row.views
        platform = platform_for_source(row.source)
        if platform:
            totals["social_sessions"] += row.sessions

        source_key = (row.source, row.medium)
        entry = by_source.setdefault(
            source_key,
            {"source": row.source, "medium": row.medium, "platform": platform, "sessions": 0, "engaged_sessions": 0},
        )
        entry["sessions"] += row.sessions
        entry["engaged_sessions"] += row.engaged_sessions

        if not platform:
            continue
        bucket = by_platform.setdefault(platform, {"platform": platform, "sessions": 0, "engaged_sessions": 0, "sources": set()})
        bucket["sessions"] += row.sessions
        bucket["engaged_sessions"] += row.engaged_sessions
        bucket["sources"].add(row.source)

    grouped = []
    for bucket in by_platform.values():
        sessions = bucket["sessions"]
        grouped.append(
            {
                "platform": bucket["platform"],
                "label": (labels or {}).get(bucket["platform"], bucket["platform"]),
                "sessions": sessions,
                "engaged_sessions": bucket["engaged_sessions"],
                "engagement_rate": round(bucket["engaged_sessions"] / sessions, 4) if sessions else None,
                "sources": sorted(bucket["sources"]),
            }
        )
    grouped.sort(key=lambda entry: entry["sessions"], reverse=True)

    sources = sorted(by_source.values(), key=lambda entry: entry["sessions"], reverse=True)
    for entry in sources:
        entry["engagement_rate"] = (
            round(entry["engaged_sessions"] / entry["sessions"], 4) if entry["sessions"] else None
        )
    return {
        "totals": totals,
        "by_platform": grouped,
        "by_source": sources[:15],
    }
