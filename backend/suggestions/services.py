"""Rule-based + LLM-backed suggestion generation (ORM only)."""
import json
import os
import urllib.request
from datetime import timedelta

from django.db.models import Avg, Sum
from django.utils import timezone

from ads.models import AdSpend
from campaigns.models import Campaign
from content.models import ContentItem
from results.models import DailyMetric


def campaign_snapshot(campaign: Campaign) -> dict:
    metrics = DailyMetric.objects.filter(campaign=campaign).aggregate(
        revenue=Sum("revenue"), orders=Sum("orders"), spend=Sum("spend"),
        avg_ctr=Avg("ctr"), avg_roas=Avg("roas"),
    )
    ads = AdSpend.objects.filter(campaign=campaign).aggregate(
        spend=Sum("spend"), impressions=Sum("impressions"),
        clicks=Sum("clicks"), conversions=Sum("conversions"),
    )
    upcoming = ContentItem.objects.filter(
        campaign=campaign,
        publish_at__gte=timezone.now(),
        publish_at__lte=timezone.now() + timedelta(days=7),
    ).count()
    return {
        "campaign": {"id": campaign.id, "name": campaign.name, "status": campaign.status, "budget": str(campaign.budget)},
        "metrics": {k: (float(v) if v is not None else 0) for k, v in metrics.items()},
        "ads": {k: (float(v) if v is not None else 0) for k, v in ads.items()},
        "upcoming_content_7d": upcoming,
    }


def rule_suggestions(campaign: Campaign) -> list[dict]:
    snap = campaign_snapshot(campaign)
    out = []
    m, a = snap["metrics"], snap["ads"]
    ctr = m["avg_ctr"]
    roas = m["avg_roas"]
    if ctr and ctr < 1.0:
        out.append({"title": "Refresh creative", "text": f"Avg CTR {ctr:.2f}% < 1%. Test new hook/creative on top channel this week."})
    if roas and roas >= 4.0:
        out.append({"title": "Scale winners", "text": f"ROAS {roas:.2f} >= 4. Increase budget ~20% on best ad set, keep frequency < 3."})
    if a["spend"] > 0 and a["conversions"] == 0:
        out.append({"title": "Fix targeting/landing", "text": "Spend with zero conversions. Check audience, UTM links to basket site, and landing load time."})
    if snap["upcoming_content_7d"] == 0:
        out.append({"title": "Plan next 7 days", "text": "No content scheduled. Draft 3 posts (1 promo, 1 UGC/social proof, 1 offer) and schedule them."})
    if not out:
        out.append({"title": "Hold steady", "text": "Metrics healthy. Keep cadence, log results daily, review again in 3 days."})
    for s in out:
        s["input_snapshot"] = snap
    return out


def llm_suggestions(campaign: Campaign, api_key: str | None = None, model: str = "gpt-4o-mini") -> dict:
    """Call OpenAI chat completions server-side. Raises RuntimeError if no key."""
    key = api_key or os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY not set.")
    snap = campaign_snapshot(campaign)
    rules = rule_suggestions(campaign)
    prompt = (
        "You are a performance marketing coach for a small basket e-shop. "
        "Given this JSON snapshot and rule hints, suggest 3 concrete next steps "
        "(channel, action, expected effect). Keep each under 40 words.\n\n"
        f"SNAPSHOT: {json.dumps(snap)}\nRULES: {json.dumps([r['title'] + ': ' + r['text'] for r in rules])}"
    )
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 400,
        "temperature": 0.6,
    }).encode()
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions", data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode())
    text = data["choices"][0]["message"]["content"]
    return {"text": text, "snapshot": snap}
