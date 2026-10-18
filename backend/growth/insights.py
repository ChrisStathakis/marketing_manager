"""Rule-based recommendations: what to post next, and what to stop doing.

Every rule is a condition on the logged performance plus a sentence explaining
it. There is no model and no scoring black box — the point is that the operator
can disagree with a recommendation and see exactly why it was made.

Order matters: problems first (something is leaking), then wins to repeat, then
housekeeping.
"""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from .analytics import group_by, group_stats, platform_trend, traffic_summary
from .metrics import metric_label
from .models import GrowthExperiment, PostPerformance, StatCard, TrafficSnapshot

PLATFORM_LABELS = dict(PostPerformance.PLATFORM_CHOICES)
KIND_LABELS = dict(StatCard.KIND_CHOICES)

#: The Monday-to-Sunday rhythm in ``planning.PLAN_SLOTS`` is eight posts, but
#: only about five of them are "own audience" posts worth counting here.
CADENCE_POSTS_PER_WEEK = 5
#: An experiment older than this is not an experiment any more, it is a note.
EXPERIMENT_STALE_DAYS = 21
#: Sessions a platform must send before "you are not posting there" is advice
#: rather than noise.
TRAFFIC_FLOOR = 25
#: Impressions a platform needs before it can be ranked.
IMPRESSION_FLOOR = 200
#: How much better the leader has to be before "do more of this" is honest.
MARGIN = 1.2

SEVERITY_RANK = {"warn": 0, "win": 1, "info": 2}


def percent(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:.2f}%"


def insight(
    key: str,
    severity: str,
    title: str,
    detail: str,
    evidence: list[str] | None = None,
    action: dict | None = None,
) -> dict:
    payload = {
        "id": key,
        "severity": severity,
        "title": title,
        "detail": detail,
        "evidence": [item for item in (evidence or []) if item],
    }
    if action:
        payload["action"] = action
    return payload


def collect(days: int = 30, campaign=None, today=None) -> dict:
    """Gather both windows, the traffic and the experiments as plain dicts."""
    now = timezone.now()
    since = now - timedelta(days=days)
    previous_since = since - timedelta(days=days)
    day = today or timezone.localdate()

    def posts(start, end=None) -> list:
        queryset = PostPerformance.objects.filter(posted_at__gte=start)
        if end is not None:
            queryset = queryset.filter(posted_at__lt=end)
        if campaign is not None:
            queryset = queryset.filter(campaign=campaign)
        return list(queryset)

    current = posts(since)
    previous = posts(previous_since, since)
    snapshots = list(TrafficSnapshot.objects.filter(date__gte=day - timedelta(days=days)))
    experiments = list(GrowthExperiment.objects.all())
    metric_labels = {row.metric_key: metric_label(row.metric_key) for row in current if row.metric_key}

    return {
        "days": days,
        "since": since,
        "previous_since": previous_since,
        "totals": group_stats(current),
        "previous_totals": group_stats(previous),
        "by_platform": group_by(current, "platform", PLATFORM_LABELS),
        "by_kind": group_by(current, "kind", KIND_LABELS),
        "by_metric": group_by(current, "metric_key", metric_labels),
        "trend": platform_trend(current, previous, PLATFORM_LABELS),
        "traffic": traffic_summary(snapshots, PLATFORM_LABELS),
        "running": [item for item in experiments if item.status == "running"],
        "ideas": [item for item in experiments if item.status == "idea"],
        #: Raw rows for the rules that inspect individual posts, not aggregates.
        "posts": current,
    }


# -- rules ------------------------------------------------------------------
def _rule_no_data(ctx: dict):
    if ctx["totals"]["posts"]:
        return None
    return insight(
        "no-data",
        "info",
        "Nothing logged yet",
        (
            "Log the first published post below. The rankings need roughly a week of numbers "
            "before they mean anything, so log even the posts that went nowhere."
        ),
        [f"{ctx['days']}-day window", f"Target rhythm: {CADENCE_POSTS_PER_WEEK} own posts a week"],
        action={"target": "log"},
    )


def _rule_best_platform(ctx: dict):
    ranked = [entry for entry in ctx["by_platform"] if entry["stats"]["impressions"] >= IMPRESSION_FLOOR]
    if len(ranked) < 2:
        return None
    best, runner_up = ranked[0], ranked[1]
    best_rate = best["stats"]["click_rate"] or 0.0
    next_rate = runner_up["stats"]["click_rate"] or 0.0
    if best_rate <= next_rate * MARGIN or not best_rate:
        return None
    return insight(
        "best-platform",
        "win",
        f"{best['label']} is your best channel",
        (
            f"{best['label']} turns impressions into clicks {best_rate / next_rate:.1f}× better than "
            f"{runner_up['label']}. Spend the scarce promotion time there first and let the others repurpose."
        ),
        [
            f"{best['label']}: {percent(best['stats']['click_rate'])} clicks over {best['stats']['impressions']:,} impressions",
            f"{runner_up['label']}: {percent(runner_up['stats']['click_rate'])} clicks",
        ],
    )


def _rule_traffic_never_landed(ctx: dict):
    """Clicks without sessions means a broken link or a lost tracking parameter."""
    if not ctx["traffic"]["totals"]["sessions"]:
        return None
    sessions = {row["platform"]: row["sessions"] for row in ctx["traffic"]["by_platform"]}
    leaks = [
        entry
        for entry in ctx["by_platform"]
        if entry["stats"]["clicks"] >= 5 and not sessions.get(entry["key"])
    ]
    if not leaks:
        return None
    names = ", ".join(entry["label"] for entry in leaks)
    return insight(
        "traffic-leak",
        "warn",
        f"Clicks from {names} never arrived",
        (
            "GA4 recorded no sessions from those platforms in the same window. Check the UTM link "
            "in the post, and whether the lander actually loads on mobile."
        ),
        [f"{entry['label']}: {entry['stats']['clicks']} clicks, 0 sessions" for entry in leaks],
        action={"target": "traffic"},
    )


def _rule_unlogged_traffic(ctx: dict):
    """Sessions from a platform nobody logged: either log it or stop claiming credit."""
    if not ctx["traffic"]["totals"]["sessions"]:
        return None
    logged = {entry["key"] for entry in ctx["by_platform"]}
    silent = [
        row
        for row in ctx["traffic"]["by_platform"]
        if row["platform"] not in logged and row["sessions"] >= TRAFFIC_FLOOR
    ]
    if not silent:
        return None
    return insight(
        "unlogged-traffic",
        "info",
        "Traffic is arriving from a channel you are not logging",
        (
            "GA4 is sending sessions from a platform with no post records. Those visits are "
            "invisible in the per-post ranking — either log the posts or stop counting them."
        ),
        [
            f"{row['label']}: {row['sessions']:,} sessions ({percent(row['engagement_rate'])} engaged)"
            for row in silent
        ],
        action={"target": "log"},
    )


def _rule_best_kind(ctx: dict):
    ranked = [entry for entry in ctx["by_kind"] if entry["stats"]["posts"] >= 2]
    if len(ranked) < 2:
        return None
    best = ranked[0]
    best_rate = best["stats"]["click_rate"] or 0.0
    if not best_rate:
        return None
    return insight(
        "best-kind",
        "win",
        f"{best['label']} cards pull the most clicks",
        (
            f"Across {best['stats']['posts']} posts, {best['label'].lower()} cards click through at "
            f"{percent(best_rate)}. Build the next week around that format."
        ),
        [
            f"{entry['label']}: {percent(entry['stats']['click_rate'])} over {entry['stats']['posts']} posts"
            for entry in ranked[:3]
        ],
        action={"target": "builder", "kind": best["key"]},
    )


def _rule_best_metric(ctx: dict):
    ranked = [entry for entry in ctx["by_metric"] if entry["stats"]["posts"] >= 2]
    if len(ranked) < 2:
        return None
    best = ranked[0]
    best_rate = best["stats"]["click_rate"] or 0.0
    if not best_rate:
        return None
    return insight(
        "best-metric",
        "win",
        f"“{best['label']}” is the metric people click",
        (
            "The same platform and the same audience, so the difference is the subject. "
            "Make this the Tuesday metric of the day for the next two weeks."
        ),
        [
            f"{entry['label']}: {percent(entry['stats']['click_rate'])} over {entry['stats']['posts']} posts"
            for entry in ranked[:3]
        ],
        action={"target": "builder", "metric": best["key"]},
    )


def _rule_impressions_without_interest(ctx: dict):
    """A big reach with a poor click rate: the post travelled, the promise did not."""
    posts = [row for row in ctx["posts"] if row.impressions >= IMPRESSION_FLOOR]
    if len(posts) < 3:
        return None
    impressions = sorted(row.impressions for row in posts)
    median = impressions[len(impressions) // 2]
    weak = [
        row
        for row in posts
        if row.impressions >= median * 2 and row.click_rate is not None and row.click_rate < (ctx["totals"]["click_rate"] or 0) / 2
    ]
    if not weak:
        return None
    return insight(
        "reach-without-clicks",
        "warn",
        "One post reached far and converted badly",
        (
            "Well above your median reach but less than half your usual click rate: the hook stopped "
            "them, the follow-up did not. Read the outreach copy again before repeating the angle."
        ),
        [
            f"{row.get_platform_display()}: {row.impressions:,} impressions, {percent(row.click_rate)} clicks"
            for row in weak[:3]
        ],
    )


def _rule_cadence(ctx: dict):
    expected = CADENCE_POSTS_PER_WEEK * max(1, ctx["days"] // 7)
    actual = ctx["totals"]["posts"]
    if not actual or actual >= expected / 2:
        return None
    return insight(
        "behind-cadence",
        "info",
        "You are behind the rhythm",
        (
            f"{actual} posts logged against roughly {expected} expected in {ctx['days']} days. "
            "Missing days is the normal way organic growth stalls — fill next week's calendar before Monday."
        ),
        [f"{actual} logged of ~{expected} expected"],
        action={"target": "plan"},
    )


def _rule_stale_experiments(ctx: dict):
    if not ctx["running"]:
        return None
    today = timezone.localdate()
    stale = [
        item
        for item in ctx["running"]
        if item.started_on and (today - item.started_on).days >= EXPERIMENT_STALE_DAYS
    ]
    if not stale:
        return None
    return insight(
        "stale-experiments",
        "info",
        "An experiment has been running too long",
        (
            f"Running for {EXPERIMENT_STALE_DAYS}+ days with no result. Close it with a verdict — "
            "a finished experiment teaches something, a running one only takes up attention."
        ),
        [f"{item.name} (since {item.started_on:%Y-%m-%d})" for item in stale],
    )


def _rule_idea_backlog(ctx: dict):
    if len(ctx["ideas"]) < 3:
        return None
    return insight(
        "idea-backlog",
        "info",
        f"{len(ctx['ideas'])} experiments are still ideas",
        "Pick one and start it this week; a list of untested hypotheses is the same as no hypotheses.",
        [item.name for item in ctx["ideas"][:4]],
    )


RULES = (
    _rule_no_data,
    _rule_traffic_never_landed,
    _rule_best_platform,
    _rule_best_kind,
    _rule_best_metric,
    _rule_impressions_without_interest,
    _rule_unlogged_traffic,
    _rule_cadence,
    _rule_stale_experiments,
    _rule_idea_backlog,
)


def next_cards(ctx: dict) -> list[dict]:
    """Card settings worth trying next, ready to drop into the studio form."""
    cards: list[dict] = []

    metric_leaders = [entry for entry in ctx["by_metric"] if entry["stats"]["posts"] >= 2 and entry["stats"]["click_rate"]]
    if metric_leaders:
        best = metric_leaders[0]
        cards.append(
            {
                "kind": "metric",
                "metric": best["key"],
                "country": None,
                "reason": f"“{best['label']}” posts click at {percent(best['stats']['click_rate'])}.",
            }
        )

    kind_leaders = [entry for entry in ctx["by_kind"] if entry["stats"]["posts"] >= 2 and entry["stats"]["click_rate"]]
    if kind_leaders:
        best_kind = kind_leaders[0]
        # The metric suggestion above is already a "metric" card; do not repeat it.
        if not metric_leaders or best_kind["key"] != "metric":
            cards.append(
                {
                    "kind": best_kind["key"],
                    "metric": None,
                    "country": None,
                    "reason": f"{best_kind['label']} is the strongest format so far.",
                }
            )

    if not cards:
        cards.append(
            {
                "kind": "round_recap",
                "metric": None,
                "country": None,
                "reason": "The five-number recap is the safest start: it needs no audience knowledge.",
            }
        )
    return cards


def build_insights(days: int = 30, campaign=None, today=None) -> dict:
    """The report plus the recommendations derived from it."""
    ctx = collect(days=days, campaign=campaign, today=today)
    found = []
    for rule in RULES:
        result = rule(ctx)
        if result:
            found.append(result)
    found.sort(key=lambda entry: SEVERITY_RANK.get(entry["severity"], 3))

    return {
        "days": ctx["days"],
        "since": ctx["since"],
        "previous_since": ctx["previous_since"],
        "totals": ctx["totals"],
        "previous_totals": ctx["previous_totals"],
        "insights": found,
        "next_cards": next_cards(ctx),
    }
