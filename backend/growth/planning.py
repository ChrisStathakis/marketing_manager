"""Seed a week of organic posts into the existing calendar and to-do list.

The rhythm is fixed on purpose: one decision a week ("is this round's data
fresh?") beats deciding every day what to post. Monday recap, Tuesday metric,
Wednesday comparison, Friday numbers, Sunday digest — the rest of the week is
repurposing, which the card studio makes cheap.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from urllib.parse import urlencode

from django.utils import timezone

from content.models import ContentItem
from plans.models import Task

#: offset = days after the Monday the plan starts on.
PLAN_SLOTS: tuple[dict, ...] = (
    {"offset": 0, "hour": 11, "platform": "x", "kind": "round_recap", "title": "Round recap — {round}"},
    {"offset": 1, "hour": 18, "platform": "x", "kind": "metric", "title": "Metric of the day — {round}"},
    {"offset": 2, "hour": 20, "platform": "x", "kind": "comparison", "title": "Head to head — {round}"},
    {"offset": 3, "hour": 19, "platform": "instagram", "kind": "round_recap", "title": "Carousel — {round}"},
    {"offset": 4, "hour": 21, "platform": "x", "kind": "player", "title": "Post-round numbers — {round}"},
    {"offset": 4, "hour": 21, "platform": "reddit", "kind": "round_recap", "title": "Reddit value post — {round}"},
    {"offset": 5, "hour": 19, "platform": "tiktok", "kind": "metric", "title": "Short — {round}"},
    {"offset": 6, "hour": 11, "platform": "telegram", "kind": "round_recap", "title": "Weekly digest — {round}"},
)

DEFAULT_BRIEFS = {
    "round_recap": "Pull five leaders from the round-recap card. Numbers first, no hype.",
    "metric": "One proprietary metric. Explain it in one line, then show the number.",
    "comparison": "Two players, same metric set. Let the better number win visually.",
    "player": "Post-round line for one player from a priority market.",
}


def site_link(site_url: str, platform: str, utm_campaign: str) -> str:
    query = urlencode({"utm_source": platform, "utm_medium": "social", "utm_campaign": utm_campaign})
    return f"{site_url.rstrip('/')}/?{query}"


def build_plan(
    round_label: str,
    start_date: date,
    campaign,
    channels: dict[str, object],
    site_url: str,
    briefs: dict[str, str] | None = None,
) -> list[dict]:
    """Return the posts for one week. No database writes."""
    utm_campaign = campaign.utm_campaign or "organic-growth"
    merged_briefs = {**DEFAULT_BRIEFS, **(briefs or {})}
    plan = []
    for slot in PLAN_SLOTS:
        day = start_date + timedelta(days=slot["offset"])
        publish_at = timezone.make_aware(datetime.combine(day, time(slot["hour"])))
        title = slot["title"].format(**{"round": round_label})
        plan.append(
            {
                "title": title,
                "kind": slot["kind"],
                "platform": slot["platform"],
                "channel": channels.get(slot["platform"]),
                "publish_at": publish_at,
                "copy": merged_briefs.get(slot["kind"], ""),
                "link": site_link(site_url, slot["platform"], utm_campaign),
                "utm_source": slot["platform"],
                "utm_medium": "social",
                "utm_campaign": utm_campaign,
            }
        )
    return plan


def seed_plan(plan: list[dict], campaign) -> dict:
    """Create the calendar entries and matching to-dos, idempotently."""
    created_items, skipped, created_tasks = [], 0, 0
    for entry in plan:
        item, was_created = ContentItem.objects.get_or_create(
            campaign=campaign,
            channel=entry["channel"],
            title=entry["title"],
            publish_at=entry["publish_at"],
            defaults={
                "copy": entry["copy"],
                "link": entry["link"],
                "utm_source": entry["utm_source"],
                "utm_medium": entry["utm_medium"],
                "utm_campaign": entry["utm_campaign"],
                "status": "scheduled",
            },
        )
        if was_created:
            created_items.append(item)
        else:
            skipped += 1

        task_title = f"Publish {entry['platform']}: {entry['title']}"
        _, task_created = Task.objects.get_or_create(
            campaign=campaign,
            title=task_title,
            due_date=entry["publish_at"].date(),
            defaults={"notes": entry["copy"]},
        )
        created_tasks += int(task_created)

    return {
        "items": created_items,
        "created": len(created_items),
        "skipped": skipped,
        "tasks": created_tasks,
    }
