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


def site_link(
    site_url: str,
    platform: str,
    utm_campaign: str,
    utm_content: str = "",
    path: str = "",
) -> str:
    params = {"utm_source": platform, "utm_medium": "social", "utm_campaign": utm_campaign}
    if utm_content:
        params["utm_content"] = utm_content
    query = urlencode(params)
    landing_path = (path or "/").strip()
    if not landing_path.startswith("/"):
        landing_path = f"/{landing_path}"
    landing_path = landing_path.rstrip("/") or "/"
    return f"{site_url.rstrip('/')}{landing_path}?{query}"


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
                "link": site_link(
                    site_url,
                    slot["platform"],
                    utm_campaign,
                    path=getattr(campaign, "landing_path", "") or "",
                ),
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


def _format_template(text: str, **values) -> str:
    """Format only known placeholders; a stray brace must not break a run."""
    try:
        return (text or "").format(**values)
    except (KeyError, IndexError, ValueError):
        return text or ""


def build_playbook_plan(
    playbook,
    campaign,
    start_date: date,
    *,
    channels: dict[str, object] | None = None,
    site_url: str = "https://catchandstats.com",
    locales: list[str] | tuple[str, ...] | None = None,
    platforms: list[str] | tuple[str, ...] | None = None,
    round_label: str = "",
    skip_past: bool = False,
    now=None,
) -> list[dict]:
    """Expand a playbook into dated posts. No database writes.

    Dates are always derived from ``start_date + slot.day_offset``. There is no
    calendar constant in this function, so running the same playbook in
    November and again in January produces two different schedules.
    """
    selected_locales = [str(item) for item in (locales or playbook.default_locales or ["en"])]
    if not selected_locales:
        selected_locales = ["en"]
    selected_platforms = {str(item) for item in (platforms or playbook.default_platforms or [])}
    channels = channels or {}
    utm_campaign = campaign.utm_campaign or "organic-growth"
    moment = now or timezone.now()
    plan: list[dict] = []

    for slot in playbook.slots.all():
        if selected_platforms and slot.platform not in selected_platforms and not slot.is_task_only:
            continue
        slot_locales = [str(item) for item in (slot.locales or [])]
        if slot.is_task_only:
            # A review task is not a language-specific post; one row is enough.
            effective_locales = [(slot_locales or selected_locales or ["en"])[0]]
        elif slot_locales:
            effective_locales = [locale for locale in slot_locales if locale in selected_locales]
        else:
            effective_locales = list(selected_locales)
        if not effective_locales:
            continue

        for locale in effective_locales:
            day = start_date + timedelta(days=slot.day_offset)
            slot_time = slot.time
            if isinstance(slot_time, str):
                try:
                    slot_time = time.fromisoformat(slot_time)
                except ValueError:
                    slot_time = time(12, 0)
            publish_at = timezone.make_aware(datetime.combine(day, slot_time))
            if skip_past and publish_at < moment:
                continue

            values = {
                "round": round_label or "this round",
                "locale": locale.upper(),
                "platform": slot.platform,
                "format": slot.format,
            }
            title = _format_template(slot.title_template, **values)
            if len(effective_locales) > 1 and f"[{locale.upper()}]" not in title:
                title = f"{title} [{locale.upper()}]"
            utm_content = _format_template(
                slot.utm_content_template or f"{slot.format}_{locale}", **values
            )
            plan.append(
                {
                    "slot_id": slot.id,
                    "title": title,
                    "kind": slot.content_kind,
                    "platform": slot.platform,
                    "format": slot.format,
                    "locale": locale,
                    "channel": channels.get(slot.platform),
                    "publish_at": publish_at,
                    "copy": slot.brief,
                    "notes": slot.notes,
                    "link": site_link(
                        site_url,
                        slot.platform,
                        utm_campaign,
                        utm_content,
                        path=getattr(campaign, "landing_path", "") or "",
                    ),
                    "utm_source": slot.platform,
                    "utm_medium": "social",
                    "utm_campaign": utm_campaign,
                    "utm_content": utm_content,
                    "asset_required": slot.asset_required,
                    "paid_budget": float(slot.paid_budget or 0),
                    "is_task_only": slot.is_task_only,
                    "brief": slot.brief,
                }
            )
    return plan


def seed_playbook_plan(plan: list[dict], campaign, *, create_tasks: bool = True) -> dict:
    """Create playbook posts/tasks idempotently for one campaign."""
    created_items, created_tasks, skipped_task_only = [], 0, 0
    for entry in plan:
        if entry.get("is_task_only"):
            skipped_task_only += 1
            if create_tasks:
                _, task_created = Task.objects.get_or_create(
                    campaign=campaign,
                    title=entry["title"],
                    due_date=entry["publish_at"].date(),
                    defaults={"notes": entry.get("notes") or entry.get("copy") or ""},
                )
                created_tasks += int(task_created)
            continue

        item, was_created = ContentItem.objects.get_or_create(
            campaign=campaign,
            channel=entry["channel"],
            title=entry["title"],
            publish_at=entry["publish_at"],
            defaults={
                "copy": entry.get("copy", ""),
                "link": entry["link"],
                "utm_source": entry["utm_source"],
                "utm_medium": entry["utm_medium"],
                "utm_campaign": entry["utm_campaign"],
                "utm_content": entry.get("utm_content", ""),
                "locale": entry.get("locale", ""),
                "format": entry.get("format", ""),
                "content_kind": entry.get("kind", ""),
                "status": "scheduled",
                "notes": entry.get("notes", ""),
            },
        )
        if was_created:
            created_items.append(item)

        if create_tasks:
            task_title = f"Publish {entry['platform']}: {entry['title']}"
            _, task_created = Task.objects.get_or_create(
                campaign=campaign,
                title=task_title,
                due_date=entry["publish_at"].date(),
                defaults={"notes": entry.get("copy") or entry.get("brief") or ""},
            )
            created_tasks += int(task_created)

    missing = sorted(
        {entry["platform"] for entry in plan if not entry.get("is_task_only") and entry["channel"] is None}
    )
    return {
        "items": created_items,
        "created": len(created_items),
        "skipped": len(plan) - len(created_items) - skipped_task_only,
        "tasks": created_tasks,
        "task_only": skipped_task_only,
        "missing_channels": missing,
    }
