"""API for the organic-growth tools.

Read-heavy by design: the public site is the source of truth, this app shapes
its numbers into cards and captions, and a person decides what gets published.
"""

from __future__ import annotations

import csv
import io
import zipfile
from datetime import date, timedelta

from django.conf import settings
from django.core.files.base import ContentFile
from django.db.models import Count, Sum
from django.http import HttpResponse
from django.utils import timezone
from django.utils.text import slugify
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ads.models import AdSpend
from campaigns.models import Campaign
from campaigns.serializers import CampaignSerializer
from channels.models import Channel
from content.models import ContentItem
from content.serializers import ContentItemSerializer
from google_sync import ga4
from google_sync.services import PROVIDER as GA4_PROVIDER
from google_sync.services import SyncNotConfigured
from integrations.services import credential_status, record_sync

from . import analytics
from . import search_console as search_console_service
from . import traffic as traffic_service
from .builders import build_spec, build_top8_carousel, display_name
from .captions import FULL_LOCALES, LOCALES, PLATFORMS, build_captions
from .cards import SIZES, render_card
from .datasource import (
    COUNTRY_LABELS,
    PRIORITY_TEAMS,
    CatchAndStatsClient,
    DatasourceError,
    previous_team_advanced_table,
    season_table,
    search_players,
    team_advanced_table,
)
from .insights import KIND_LABELS, build_insights
from .instagram import (
    InstagramError,
    InstagramNotConfigured,
    InstagramRateLimited,
    InstagramSessionInvalid,
)
from .instagram_service import PROVIDER as INSTAGRAM_PROVIDER
from .instagram_service import get_client, mark_failed, resolve_post, sync_post
from .metrics import METRICS, metric_label
from .models import (
    Boost,
    CardSet,
    GrowthExperiment,
    HashtagSet,
    InstagramComment,
    InstagramTrackedPost,
    KpiTarget,
    Playbook,
    PlaybookSlot,
    PostPerformance,
    StatCard,
    TrafficSnapshot,
    LOCALE_CHOICES,
)
from .planning import build_plan, build_playbook_plan, seed_plan, seed_playbook_plan, site_link
from .serializers import (
    BoostSerializer,
    CardSetSerializer,
    GrowthExperimentSerializer,
    HashtagSetSerializer,
    InstagramCommentSerializer,
    InstagramTrackedPostSerializer,
    KpiTargetSerializer,
    PlaybookSerializer,
    PostPerformanceSerializer,
    StatCardSerializer,
    TrafficSnapshotSerializer,
)
from .sources import SOURCE_PLATFORMS

PLATFORM_LABELS = dict(PostPerformance.PLATFORM_CHOICES)
MAX_DAYS = 365
DEFAULT_KPI_TARGETS = (
    ("impressions", 150000),
    ("saves", 400),
    ("shares", 250),
    ("profile_visits", 800),
    ("clicks", 900),
    ("signups", 60),
    ("upvote_ratio", 0.9),
    ("search_clicks", 250),
    ("search_impressions", 5000),
    ("search_ctr", 0.05),
)


def _bad_request(message: str) -> Response:
    return Response({"detail": message}, status=status.HTTP_400_BAD_REQUEST)


def _upstream_error(message: str) -> Response:
    return Response({"detail": message}, status=status.HTTP_502_BAD_GATEWAY)


def _rate_limited(message: str) -> Response:
    return Response({"detail": message}, status=status.HTTP_429_TOO_MANY_REQUESTS)


def _site_url() -> str:
    return getattr(settings, "CATCHANDSTATS_SITE_URL", "https://catchandstats.com")


def clamp_days(raw, default: int = 30) -> int:
    """Parsed ``days`` for the growth windows, clamped to 1..365."""
    try:
        return max(1, min(int(raw), MAX_DAYS))
    except (TypeError, ValueError):
        return default


def _campaign_id(raw):
    """Campaign pk from a query parameter, or ``None`` for "every campaign"."""
    try:
        return int(raw) if raw not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _seasons() -> tuple[list[dict], str]:
    """Season list plus any non-fatal warning (stale cache, retried reads)."""
    client = CatchAndStatsClient()
    try:
        rows = client.seasons()
    except DatasourceError as exc:
        return [], str(exc)
    return rows, "; ".join(client.warnings)


def _table_meta(table: dict) -> dict:
    """Provenance for a table: when it was fetched, and whether it is stale."""
    return {
        "season": table.get("season"),
        "fetched_at": table.get("fetched_at"),
        "stale": bool(table.get("stale")),
        "warning": table.get("warning") or "",
    }


def _resolve_spec(payload: dict) -> dict:
    """Accept a ready spec, or build one from a card kind + data selection."""
    spec = payload.get("spec")
    if isinstance(spec, dict) and spec.get("title"):
        return spec
    kind = payload.get("kind") or "metric"
    teams = payload.get("teams")
    if isinstance(teams, str):
        teams = [item for item in teams.split(",") if item]
    if kind in ("team", "team_delta", "top8"):
        table = team_advanced_table(payload.get("season"), refresh=bool(payload.get("refresh")))
        previous = previous_team_advanced_table(payload.get("season"))
        return build_spec(
            table,
            kind,
            teams=teams,
            title=payload.get("title") or None,
            previous_table=previous,
            top_n=int(payload.get("top_n") or 8),
        )
    table = season_table(payload.get("season"), refresh=bool(payload.get("refresh")))
    return build_spec(
        table,
        kind,
        player_id=payload.get("player"),
        opponent_id=payload.get("opponent"),
        metric=payload.get("metric"),
        country=payload.get("country") or None,
        story=payload.get("story") or None,
        teams=teams,
        title=payload.get("title") or None,
    )


def _hashtag_bank() -> dict[str, list[str]]:
    """Default hashtag sets keyed by locale, overridden per platform when set."""
    bank: dict[str, list[str]] = {}
    for row in HashtagSet.objects.filter(is_default=True).order_by("locale", "platform"):
        key = f"{row.platform}:{row.locale}" if row.platform else row.locale
        bank[key] = list(row.tags or [])
    return bank


def _parse_date(raw, field: str = "start_date"):
    if raw in (None, ""):
        return timezone.localdate(), None
    try:
        return date.fromisoformat(str(raw)), None
    except (TypeError, ValueError):
        return None, f"{field} must be an ISO date (YYYY-MM-DD)."


def _parse_list(raw, fallback: list | None = None) -> list:
    if raw in (None, ""):
        return list(fallback or [])
    if isinstance(raw, str):
        return [item.strip() for item in raw.split(",") if item.strip()]
    if isinstance(raw, (list, tuple)):
        return [str(item) for item in raw if str(item).strip()]
    return list(fallback or [])


class GrowthMetaView(APIView):
    """Everything the studio needs to render its form controls."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        season_rows, warning = _seasons()
        default_season = next(
            (row for row in season_rows if row.get("default_season") or row.get("active")),
            season_rows[0] if season_rows else None,
        )
        return Response(
            {
                "seasons": season_rows,
                "default_season": default_season,
                "priority_teams": PRIORITY_TEAMS,
                "country_labels": COUNTRY_LABELS,
                "kinds": StatCard.KIND_CHOICES,
                "formats": StatCard.FORMAT_CHOICES,
                "content_formats": PlaybookSlot._meta.get_field("format").choices,
                "playbook_platforms": PlaybookSlot._meta.get_field("platform").choices,
                "content_locales": LOCALE_CHOICES,
                "sizes": SIZES,
                "platforms": [choice for choice in PostPerformance.PLATFORM_CHOICES if choice[0] in PLATFORMS],
                "log_platforms": PostPerformance.PLATFORM_CHOICES,
                "locales": LOCALES,
                "full_locales": sorted(FULL_LOCALES),
                "kpi_metrics": KpiTarget._meta.get_field("metric").choices,
                "hashtag_sets": HashtagSetSerializer(HashtagSet.objects.all(), many=True).data,
                "metrics": [
                    {"key": key, "label": metric.label, "short": metric.short, "digits": metric.digits}
                    for key, metric in METRICS.items()
                ],
                "site_url": _site_url(),
                "sources": SOURCE_PLATFORMS,
                "ga4_configured": credential_status(GA4_PROVIDER)["configured"],
                "instagram_configured": credential_status(INSTAGRAM_PROVIDER)["configured"],
                "instagram_enabled": _instagram_enabled(),
                "can_sync": bool(request.user.is_staff),
                "warning": warning,
            }
        )


class GrowthPlayersView(APIView):
    """Searchable player list for the picker, ordered by any metric."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        params = request.query_params
        try:
            table = season_table(params.get("season"))
        except DatasourceError as exc:
            return _upstream_error(str(exc))

        rows = search_players(
            table,
            params.get("search", ""),
            country=params.get("country") or None,
            metric=params.get("metric") or None,
        )
        ordering = params.get("ordering") or "-score"
        field = ordering.lstrip("-")
        if field in METRICS:
            rows = [row for row in rows if row["metrics"].get(field) is not None]
            rows.sort(key=lambda row: row["metrics"][field], reverse=ordering.startswith("-"))
        else:
            rows.sort(key=lambda row: row["player"])

        try:
            page = max(1, int(params.get("page", 1)))
        except (TypeError, ValueError):
            page = 1
        try:
            size = min(max(1, int(params.get("page_size", 50))), 200)
        except (TypeError, ValueError):
            size = 50
        start = (page - 1) * size

        results = [
            {
                "id": row["id"],
                "player": row["player"],
                "name": display_name(row["player"]),
                "team": row["team"],
                "country": row.get("country"),
                "country_label": COUNTRY_LABELS.get(row.get("country") or "", ""),
                "position": row.get("position"),
                "season": row.get("season"),
                "metrics": row["metrics"],
            }
            for row in rows[start : start + size]
        ]
        return Response(
            {
                "count": len(rows),
                "page": page,
                "page_size": size,
                **_table_meta(table),
                "teams": sorted({row["team"] for row in table.get("players", []) if row.get("team")}),
                "results": results,
            }
        )


class GrowthTeamsView(APIView):
    """Advanced team table for the builder's team picker."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        params = request.query_params
        try:
            table = team_advanced_table(params.get("season"), refresh=params.get("refresh") == "1")
        except DatasourceError as exc:
            return _upstream_error(str(exc))
        return Response(
            {
                "results": table.get("teams", []),
                **_table_meta(table),
            }
        )


class GrowthSuggestView(APIView):
    """Auto-pick the next post: the data chooses, the editor approves."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        params = request.query_params
        platform = params.get("platform") or "x"
        utm_campaign = params.get("utm_campaign") or "organic-growth"
        try:
            kind = params.get("kind") or "metric"
            table = (
                team_advanced_table(params.get("season"))
                if kind in ("team", "team_delta", "top8")
                else season_table(params.get("season"))
            )
            spec = _resolve_spec(params)
        except DatasourceError as exc:
            return _upstream_error(str(exc))
        except ValueError as exc:
            return _bad_request(str(exc))
        return Response(
            {
                "spec": spec,
                **_table_meta(table),
                "link": site_link(
                    _site_url(),
                    platform,
                    utm_campaign,
                    params.get("utm_content") or "",
                ),
            }
        )


class CardPreviewView(APIView):
    """POST a spec (or a kind + filters) and get a PNG back, nothing saved."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        payload = request.data if isinstance(request.data, dict) else {}
        card_format = payload.get("format") or "x"
        if card_format not in SIZES:
            return _bad_request(f"Unknown format {card_format!r}. Use one of {', '.join(SIZES)}.")
        try:
            spec = _resolve_spec(payload)
        except DatasourceError as exc:
            return _upstream_error(str(exc))
        except ValueError as exc:
            return _bad_request(str(exc))
        png = render_card(spec, card_format)
        response = HttpResponse(png, content_type="image/png")
        response["Content-Disposition"] = f'inline; filename="card-{card_format}.png"'
        response["Cache-Control"] = "no-store"
        return response


class StatCardViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    queryset = StatCard.objects.select_related("campaign").all()
    serializer_class = StatCardSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["kind", "format", "campaign", "card_set"]
    ordering_fields = ["created_at", "position"]

    def create(self, request, *args, **kwargs):
        payload = request.data if isinstance(request.data, dict) else {}
        card_format = payload.get("format") or "x"
        if card_format not in SIZES:
            return _bad_request(f"Unknown format {card_format!r}. Use one of {', '.join(SIZES)}.")
        campaign = None
        if payload.get("campaign"):
            campaign = Campaign.objects.filter(pk=payload["campaign"]).first()
            if campaign is None:
                return _bad_request("Unknown campaign.")
        try:
            spec = _resolve_spec(payload)
        except DatasourceError as exc:
            return _upstream_error(str(exc))
        except ValueError as exc:
            return _bad_request(str(exc))

        png = render_card(spec, card_format)
        card = StatCard(
            campaign=campaign,
            kind=spec.get("kind") or "player",
            format=card_format,
            title=spec.get("title") or "",
            subtitle=spec.get("subtitle") or "",
            payload=spec,
        )
        card.image.save(f"card-{card_format}.png", ContentFile(png), save=False)
        card.save()
        serializer = self.get_serializer(card)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="recaption")
    def recaption(self, request, pk=None):
        card = self.get_object()
        payload = request.data if isinstance(request.data, dict) else {}
        link = payload.get("link") or site_link(
            _site_url(),
            payload.get("platform") or "x",
            payload.get("utm_campaign") or "organic-growth",
            payload.get("utm_content") or "",
        )
        drafts = build_captions(
            card.payload,
            link=link,
            platforms=payload.get("platforms"),
            locales=payload.get("locales"),
            hashtags=_hashtag_bank(),
        )
        return Response({"drafts": drafts, "link": link})


class CaptionDraftView(APIView):
    """POST a spec, get copy for every platform and language."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        payload = request.data if isinstance(request.data, dict) else {}
        try:
            spec = _resolve_spec(payload)
        except DatasourceError as exc:
            return _upstream_error(str(exc))
        except ValueError as exc:
            return _bad_request(str(exc))

        link = payload.get("link")
        utm_campaign = payload.get("utm_campaign") or "organic-growth"
        utm_content = payload.get("utm_content") or ""
        if link:
            links: dict[str, str] = {}
        else:
            # Reddit gets no tracked URL by default: a naked UTM link in a text
            # post reads like an ad and trips the self-promotion rules.
            links = {
                platform: site_link(_site_url(), platform, utm_campaign, utm_content)
                for platform in PLATFORMS
                if platform != "reddit"
            }
            link = site_link(_site_url(), "x", utm_campaign, utm_content)
        drafts = build_captions(
            spec,
            link=link,
            platforms=payload.get("platforms") or PLATFORMS,
            locales=payload.get("locales") or LOCALES,
            links=links,
            hashtags=_hashtag_bank(),
        )
        return Response({"spec": spec, "link": link, "drafts": drafts})


class PlanSeedView(APIView):
    """Create next week's calendar entries and to-dos in one call."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        payload = request.data if isinstance(request.data, dict) else {}
        campaign = Campaign.objects.filter(pk=payload.get("campaign")).first()
        if campaign is None:
            return _bad_request("Choose a campaign to attach the plan to.")

        raw_start = payload.get("start_date")
        try:
            start = date.fromisoformat(raw_start) if raw_start else timezone.localdate()
        except (TypeError, ValueError):
            return _bad_request("start_date must be an ISO date (YYYY-MM-DD).")
        # Snap to the Monday of that week so the rhythm stays consistent.
        start = start - timedelta(days=start.weekday())
        round_label = (payload.get("round_label") or "this round").strip()

        briefs: dict[str, str] = {}
        warning = ""
        try:
            table = season_table(payload.get("season"))
            recap = build_spec(table, "round_recap")
            if recap.get("rows"):
                briefs["round_recap"] = "Leaders: " + "; ".join(
                    f"{row['label']} {row['value']} ({row['note']})" for row in recap["rows"][:5]
                )
            comparison = build_spec(table, "comparison", country=payload.get("country") or None)
            briefs["comparison"] = f"{comparison['title']} — " + "; ".join(
                f"{row['label']}: {row['left']} vs {row['right']}" for row in comparison["rows"]
            )
            metric = build_spec(table, "metric", country=payload.get("country") or None)
            briefs["metric"] = f"{metric['subtitle']} — {metric['headline']} {metric['headline_label']}."
            player = build_spec(table, "player", country=payload.get("country") or None)
            briefs["player"] = f"{player['title']} — {player['headline']} {player['headline_label']}."
        except (DatasourceError, ValueError) as exc:
            warning = f"Plan created with generic briefs: {exc}"

        supplied = payload.get("briefs")
        if isinstance(supplied, dict):
            briefs.update({str(key): str(value) for key, value in supplied.items()})

        channels = {
            channel.channel_type: channel
            for channel in Channel.objects.filter(channel_type__in=PLATFORM_LABELS)
        }
        plan = build_plan(round_label, start, campaign, channels, _site_url(), briefs)
        result = seed_plan(plan, campaign)
        return Response(
            {
                "created": result["created"],
                "skipped": result["skipped"],
                "tasks": result["tasks"],
                "missing_channels": sorted({entry["platform"] for entry in plan if entry["channel"] is None}),
                "week_start": start,
                "items": ContentItemSerializer(result["items"], many=True).data,
                "warning": warning,
            },
            status=status.HTTP_201_CREATED,
        )


class PlaybookViewSet(viewsets.ModelViewSet):
    """CRUD and execution for reusable, date-free content series."""

    queryset = Playbook.objects.prefetch_related("slots").all()
    serializer_class = PlaybookSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at"]

    def _run_payload(self, request, playbook):
        payload = request.data if isinstance(request.data, dict) else {}
        start, error = _parse_date(payload.get("start_date"))
        if error:
            return None, _bad_request(error)
        locales = _parse_list(payload.get("locales"), playbook.default_locales or ["en"])
        platforms = _parse_list(payload.get("platforms"), playbook.default_platforms or [])
        round_label = (payload.get("round_label") or "").strip()
        skip_past = bool(payload.get("skip_past"))
        landing_path = (payload.get("landing_path") or "").strip()
        if landing_path and not landing_path.startswith("/"):
            landing_path = f"/{landing_path}"
        default_utm = (
            payload.get("utm_campaign")
            or slugify(f"{playbook.name}-{round_label or start.isoformat()}")
            or "organic-growth"
        )[:255]
        channels = {
            channel.channel_type: channel
            for channel in Channel.objects.filter(channel_type__in=PLATFORM_LABELS)
        }
        plan = build_playbook_plan(
            playbook,
            SimpleCampaign(default_utm, landing_path),
            start,
            channels=channels,
            site_url=_site_url(),
            locales=locales,
            platforms=platforms,
            round_label=round_label,
            skip_past=skip_past,
        )
        return {
            "payload": payload,
            "start": start,
            "locales": locales,
            "platforms": platforms,
            "round_label": round_label,
            "skip_past": skip_past,
            "utm_campaign": default_utm,
            "landing_path": landing_path,
            "channels": channels,
            "plan": plan,
        }, None

    @action(detail=True, methods=["post"])
    def preview(self, request, pk=None):
        playbook = self.get_object()
        context, error = self._run_payload(request, playbook)
        if error:
            return error
        plan = context["plan"]
        by_platform: dict[str, int] = {}
        by_locale: dict[str, int] = {}
        for entry in plan:
            by_platform[entry["platform"]] = by_platform.get(entry["platform"], 0) + 1
            by_locale[entry["locale"]] = by_locale.get(entry["locale"], 0) + 1
        end = max((entry["publish_at"].date() for entry in plan), default=context["start"])
        return Response(
            {
                "playbook": PlaybookSerializer(playbook).data,
                "start_date": context["start"],
                "end_date": end,
                "round_label": context["round_label"],
                "locales": context["locales"],
                "platforms": context["platforms"],
                "landing_path": context["landing_path"],
                "count": len(plan),
                "by_platform": [
                    {"platform": key, "label": PLATFORM_LABELS.get(key, key), "count": value}
                    for key, value in sorted(by_platform.items(), key=lambda item: -item[1])
                ],
                "by_locale": by_locale,
                "items": [
                    {
                        "title": entry["title"],
                        "kind": entry["kind"],
                        "platform": entry["platform"],
                        "platform_label": PLATFORM_LABELS.get(entry["platform"], entry["platform"]),
                        "format": entry["format"],
                        "locale": entry["locale"],
                        "publish_at": entry["publish_at"].isoformat(),
                        "link": entry["link"],
                        "utm_content": entry["utm_content"],
                        "asset_required": entry["asset_required"],
                        "paid_budget": entry["paid_budget"],
                        "is_task_only": entry["is_task_only"],
                        "channel": getattr(entry["channel"], "name", ""),
                        "missing_channel": entry["channel"] is None and not entry["is_task_only"],
                    }
                    for entry in plan
                ],
                "missing_channels": sorted(
                    {
                        entry["platform"]
                        for entry in plan
                        if entry["channel"] is None and not entry["is_task_only"]
                    }
                ),
            }
        )

    @action(detail=True, methods=["post"])
    def run(self, request, pk=None):
        playbook = self.get_object()
        context, error = self._run_payload(request, playbook)
        if error:
            return error
        payload = context["payload"]
        plan = context["plan"]
        start = context["start"]

        # Every run creates a new campaign unless the caller explicitly asks to
        # append to an existing one. That is the whole point of a playbook:
        # running it again must not overwrite last month's numbers.
        campaign = None
        if payload.get("append") and payload.get("campaign"):
            campaign = Campaign.objects.filter(pk=payload["campaign"]).first()
            if campaign is None:
                return _bad_request("Unknown campaign to append to.")
        if campaign is None:
            round_label = context["round_label"]
            name = (payload.get("name") or f"{playbook.name} · {round_label or start.isoformat()}").strip()
            utm_campaign = context["utm_campaign"]
            end = max((entry["publish_at"].date() for entry in plan), default=start)
            campaign = Campaign.objects.create(
                name=name,
                objective=playbook.description,
                status="planned",
                playbook=playbook,
                round_label=round_label,
                locales=context["locales"],
                platforms=context["platforms"],
                start_date=start,
                end_date=end,
                utm_campaign=utm_campaign,
                landing_path=context["landing_path"],
                owner=request.user,
            )

        if campaign.utm_campaign and campaign.utm_campaign != context["utm_campaign"]:
            plan = build_playbook_plan(
                playbook,
                SimpleCampaign(campaign.utm_campaign, campaign.landing_path),
                start,
                channels=context["channels"],
                site_url=_site_url(),
                locales=context["locales"],
                platforms=context["platforms"],
                round_label=context["round_label"],
                skip_past=context["skip_past"],
            )
        result = seed_playbook_plan(plan, campaign, create_tasks=payload.get("create_tasks", True))

        created_boosts = 0
        for entry in plan:
            budget = float(entry.get("paid_budget") or 0)
            if budget <= 0 or entry.get("is_task_only"):
                continue
            item = ContentItem.objects.filter(
                campaign=campaign,
                title=entry["title"],
                publish_at=entry["publish_at"],
            ).first()
            _, created = Boost.objects.get_or_create(
                campaign=campaign,
                content_item=item,
                platform=entry["platform"],
                start_date=entry["publish_at"].date(),
                defaults={
                    "status": "planned",
                    "objective": payload.get("boost_objective") or "profile_visits",
                    "daily_budget": round(budget / 7, 2),
                    "total_budget": budget,
                    "end_date": entry["publish_at"].date() + timedelta(days=7),
                    "notes": "Created from a playbook slot. Confirm targeting and dates before launch.",
                },
            )
            created_boosts += int(created)

        created_targets = 0
        if payload.get("create_targets", True):
            supplied = payload.get("kpi_targets")
            rows = supplied if isinstance(supplied, list) and supplied else [
                {"metric": metric, "target": target} for metric, target in DEFAULT_KPI_TARGETS
            ]
            for row in rows:
                if not isinstance(row, dict) or not row.get("metric"):
                    continue
                try:
                    target = float(row.get("target"))
                except (TypeError, ValueError):
                    continue
                _, created = KpiTarget.objects.get_or_create(
                    campaign=campaign,
                    metric=str(row["metric"]),
                    window_start=None,
                    window_end=None,
                    defaults={"target": target, "notes": row.get("notes", "")},
                )
                created_targets += int(created)

        return Response(
            {
                "campaign": CampaignSerializer(campaign).data,
                "created": result["created"],
                "skipped": result["skipped"],
                "tasks": result["tasks"],
                "task_only": result["task_only"],
                "missing_channels": result["missing_channels"],
                "targets_created": created_targets,
                "boosts_created": created_boosts,
                "start_date": start,
                "end_date": campaign.end_date,
                "items": ContentItemSerializer(
                    result["items"], many=True, context={"request": request}
                ).data,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def duplicate(self, request, pk=None):
        source = self.get_object()
        clone = Playbook.objects.create(
            name=(request.data.get("name") if isinstance(request.data, dict) else None)
            or f"{source.name} — copy",
            description=source.description,
            default_locales=source.default_locales,
            default_platforms=source.default_platforms,
            is_seeded=False,
        )
        for slot in source.slots.all():
            PlaybookSlot.objects.create(
                playbook=clone,
                order=slot.order,
                day_offset=slot.day_offset,
                time=slot.time,
                platform=slot.platform,
                format=slot.format,
                content_kind=slot.content_kind,
                locales=slot.locales,
                title_template=slot.title_template,
                brief=slot.brief,
                utm_content_template=slot.utm_content_template,
                asset_required=slot.asset_required,
                paid_budget=slot.paid_budget,
                is_task_only=slot.is_task_only,
                notes=slot.notes,
            )
        return Response(self.get_serializer(clone).data, status=status.HTTP_201_CREATED)


class SimpleCampaign:
    """The fields ``build_playbook_plan`` needs before a campaign exists."""

    def __init__(self, utm_campaign: str, landing_path: str = ""):
        self.utm_campaign = utm_campaign
        self.landing_path = landing_path


class CardSetViewSet(viewsets.ModelViewSet):
    """Render and store an ordered carousel (saved images live on StatCard)."""

    queryset = CardSet.objects.select_related("campaign").prefetch_related("slides").all()
    serializer_class = CardSetSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["kind", "format", "campaign"]
    ordering_fields = ["created_at"]

    def create(self, request, *args, **kwargs):
        payload = request.data if isinstance(request.data, dict) else {}
        card_format = payload.get("format") or "instagram"
        if card_format not in SIZES:
            return _bad_request(f"Unknown format {card_format!r}. Use one of {', '.join(SIZES)}.")
        campaign = None
        if payload.get("campaign"):
            campaign = Campaign.objects.filter(pk=payload["campaign"]).first()
            if campaign is None:
                return _bad_request("Unknown campaign.")

        specs = payload.get("specs")
        if not isinstance(specs, list) or not specs:
            try:
                teams = team_advanced_table(payload.get("season"))
                previous = (
                    previous_team_advanced_table(payload.get("season"))
                    if payload.get("compare_previous", True)
                    else None
                )
                specs = build_top8_carousel(
                    teams.get("teams", []),
                    top_n=int(payload.get("top_n") or 8),
                    previous_teams=(previous or {}).get("teams", []),
                    title=payload.get("title") or None,
                    include_table=bool(payload.get("include_table")),
                    include_cta=payload.get("include_cta", True),
                )
            except DatasourceError as exc:
                return _upstream_error(str(exc))
            except ValueError as exc:
                return _bad_request(str(exc))
        specs = [spec for spec in specs if isinstance(spec, dict) and spec.get("title")]
        if not specs:
            return _bad_request("No card specifications to render.")

        card_set = CardSet.objects.create(
            campaign=campaign,
            kind=payload.get("kind") or (specs[0].get("kind") or "top8"),
            format=card_format,
            title=payload.get("title") or specs[0].get("title", "Card set"),
            subtitle=payload.get("subtitle") or specs[0].get("subtitle", ""),
            payload={"specs": specs, "season": payload.get("season"), "top_n": payload.get("top_n") or 8},
        )
        for position, spec in enumerate(specs):
            png = render_card(spec, card_format)
            card = StatCard(
                campaign=campaign,
                card_set=card_set,
                kind=spec.get("kind") or "top8",
                format=card_format,
                title=spec.get("title") or "",
                subtitle=spec.get("subtitle") or "",
                payload=spec,
                position=position,
            )
            card.image.save(f"card-set-{card_set.id}-{position:02d}.png", ContentFile(png), save=False)
            card.save()
        serializer = self.get_serializer(card_set, context={"request": request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        card_set = self.get_object()
        slides = list(card_set.slides.all())
        if not slides:
            return _bad_request("This card set has no slides.")
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for index, card in enumerate(slides, start=1):
                if not card.image:
                    continue
                try:
                    with card.image.open("rb") as image:
                        archive.writestr(f"{index:02d}-{slugify(card.title) or 'slide'}.png", image.read())
                except (OSError, ValueError):
                    continue
        response = HttpResponse(buffer.getvalue(), content_type="application/zip")
        response["Content-Disposition"] = f'attachment; filename="card-set-{card_set.id}.zip"'
        return response


class KpiTargetViewSet(viewsets.ModelViewSet):
    queryset = KpiTarget.objects.select_related("campaign").all()
    serializer_class = KpiTargetSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["campaign", "metric"]
    ordering_fields = ["created_at", "target"]


class BoostViewSet(viewsets.ModelViewSet):
    queryset = Boost.objects.select_related("campaign", "content_item").all()
    serializer_class = BoostSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["campaign", "content_item", "platform", "status"]
    ordering_fields = ["created_at", "start_date", "total_budget"]


class HashtagSetViewSet(viewsets.ModelViewSet):
    queryset = HashtagSet.objects.all()
    serializer_class = HashtagSetSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["locale", "platform", "is_default"]
    search_fields = ["name", "tags"]


class PostPerformanceViewSet(viewsets.ModelViewSet):
    queryset = PostPerformance.objects.select_related("campaign", "content_item").all()
    serializer_class = PostPerformanceSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["platform", "campaign", "content_item", "kind", "format", "locale", "metric_key"]
    search_fields = ["notes", "url"]
    ordering_fields = [
        "posted_at", "impressions", "reach", "engagements", "saves", "shares",
        "profile_visits", "clicks", "signups", "created_at",
    ]


class GrowthExperimentViewSet(viewsets.ModelViewSet):
    queryset = GrowthExperiment.objects.all()
    serializer_class = GrowthExperimentSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["status"]
    search_fields = ["name", "hypothesis", "result"]
    ordering_fields = ["created_at", "started_on"]


class GrowthReportView(APIView):
    """Everything worth knowing about the window: posts, formats, traffic, trend.

    Ranked by click rate throughout. Raw volume flatters the channel you post
    most often; click rate tells you which one is worth the time.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        params = request.query_params
        days = clamp_days(params.get("days"), 30)
        campaign_id = _campaign_id(params.get("campaign"))
        now = timezone.now()
        since = now - timedelta(days=days)
        previous_since = since - timedelta(days=days)

        queryset = PostPerformance.objects.all()
        if campaign_id:
            queryset = queryset.filter(campaign_id=campaign_id)

        current = list(queryset.filter(posted_at__gte=since).order_by("-posted_at", "-created_at"))
        previous = list(queryset.filter(posted_at__gte=previous_since, posted_at__lt=since))

        by_platform = analytics.flatten(analytics.group_by(current, "platform", PLATFORM_LABELS), "platform")
        for entry in by_platform:
            rows = [row for row in current if row.platform == entry["platform"]]
            best = max(rows, key=lambda row: (row.clicks, row.impressions), default=None)
            entry["best_post"] = (
                PostPerformanceSerializer(best, context={"request": request}).data if best else None
            )

        metric_labels = {row.metric_key: metric_label(row.metric_key) for row in current if row.metric_key}
        day = timezone.localdate()
        campaign = Campaign.objects.filter(pk=campaign_id).first() if campaign_id else None
        snapshot_qs = TrafficSnapshot.objects.filter(date__gte=day - timedelta(days=days))
        if campaign is not None and campaign.utm_campaign:
            snapshot_qs = snapshot_qs.filter(campaign=campaign.utm_campaign)
        snapshots = list(snapshot_qs)
        totals = analytics.group_stats(current)
        traffic = analytics.traffic_summary(snapshots, PLATFORM_LABELS)
        search = search_console_service.build_report(campaign=campaign, days=days)
        search_campaign = search.get("campaign") or {}
        search_totals = (search_campaign.get("totals") or search.get("totals") or {}) if campaign else search.get("totals", {})

        target_rows = []
        if campaign is not None:
            spend = (
                AdSpend.objects.filter(campaign=campaign, date__gte=day - timedelta(days=days))
                .aggregate(total=Sum("spend"))
                .get("total")
                or 0
            )
            actual_by_metric = {
                **totals,
                "sessions": traffic["totals"]["sessions"],
                "search_clicks": search_totals.get("clicks", 0),
                "search_impressions": search_totals.get("impressions", 0),
                "search_ctr": search_totals.get("ctr", 0),
                "spend": float(spend),
            }
            for target in campaign.kpi_targets.all():
                actual = actual_by_metric.get(target.metric)
                ratio = (
                    round(float(actual) / target.target, 4)
                    if actual is not None and target.target
                    else None
                )
                target_rows.append(
                    {
                        **KpiTargetSerializer(target).data,
                        "actual": actual,
                        "progress": ratio,
                        "remaining": (
                            max(0, target.target - float(actual))
                            if actual is not None and target.target
                            else None
                        ),
                        "met": bool(actual is not None and actual >= target.target),
                    }
                )

        return Response(
            {
                "days": days,
                "since": since,
                "previous_since": previous_since,
                "campaign": CampaignSerializer(campaign).data if campaign else None,
                "totals": totals,
                "previous_totals": analytics.group_stats(previous),
                "kpi_targets": target_rows,
                "by_platform": by_platform,
                "by_kind": analytics.flatten(analytics.group_by(current, "kind", KIND_LABELS), "kind"),
                "by_format": analytics.flatten(
                    analytics.group_by(
                        current, "format", dict(PostPerformance._meta.get_field("format").choices)
                    ),
                    "format",
                ),
                "by_locale": analytics.flatten(
                    analytics.group_by(
                        current, "locale", dict(PostPerformance._meta.get_field("locale").choices)
                    ),
                    "locale",
                ),
                "by_metric": analytics.flatten(analytics.group_by(current, "metric_key", metric_labels), "metric"),
                "trend": analytics.platform_trend(current, previous, PLATFORM_LABELS),
                "traffic": traffic,
                "traffic_configured": credential_status(GA4_PROVIDER)["configured"],
                "search_console": search,
                "can_sync": bool(request.user.is_staff),
                "best_posts": PostPerformanceSerializer(
                    sorted(current, key=lambda row: (row.clicks, row.impressions), reverse=True)[:5],
                    many=True,
                    context={"request": request},
                ).data,
            }
        )


class GrowthInsightsView(APIView):
    """Rule-based advice: what to repeat, what is leaking, what to stop."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        params = request.query_params
        days = clamp_days(params.get("days"), 30)
        return Response(build_insights(days=days, campaign=_campaign_id(params.get("campaign"))))


class GrowthTrafficView(APIView):
    """Stored GA4 snapshots. Reads the database only — never calls Google."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        params = request.query_params
        days = clamp_days(params.get("days"), 30)
        since = timezone.localdate() - timedelta(days=days)
        queryset = TrafficSnapshot.objects.filter(date__gte=since)
        if params.get("source"):
            queryset = queryset.filter(source=params["source"])
        if params.get("campaign"):
            queryset = queryset.filter(campaign=params["campaign"])
        if params.get("content"):
            queryset = queryset.filter(content=params["content"])
        rows = list(queryset.order_by("-date", "-sessions")[:1000])
        # Prefer the newest snapshot actually imported: the credential row is
        # absent when GA4 is configured through the environment.
        latest = TrafficSnapshot.objects.order_by("-fetched_at").values_list("fetched_at", flat=True).first()
        return Response(
            {
                "days": days,
                "since": since,
                "summary": analytics.traffic_summary(rows, PLATFORM_LABELS),
                "results": TrafficSnapshotSerializer(rows, many=True).data,
                "configured": credential_status(GA4_PROVIDER)["configured"],
                "can_sync": bool(request.user.is_staff),
                "last_synced_at": latest or credential_status(GA4_PROVIDER)["last_synced_at"],
            }
        )


class GrowthSearchConsoleView(APIView):
    """Stored Google Search Console data, optionally scoped to a campaign.

    Reads the database only. Search Console has no UTM dimension, so a campaign
    filter means "pages linked by this campaign", not causal attribution.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        params = request.query_params
        days = clamp_days(params.get("days"), 30)
        campaign_id = _campaign_id(params.get("campaign"))
        campaign = Campaign.objects.filter(pk=campaign_id).first() if campaign_id else None
        return Response(search_console_service.build_report(campaign=campaign, days=days))


class GrowthTrafficSyncView(APIView):
    """Pull this window's sessions per source from GA4 (staff only, like the rest)."""

    permission_classes = [IsAdminUser]

    def post(self, request):
        payload = request.data if isinstance(request.data, dict) else {}
        raw = payload.get("days")
        if raw in (None, ""):
            days = None
        else:
            try:
                days = int(raw)
            except (TypeError, ValueError):
                return _bad_request("days must be an integer.")
            if not 1 <= days <= MAX_DAYS:
                return _bad_request(f"days must be between 1 and {MAX_DAYS}.")
        try:
            result = traffic_service.sync_organic(days=days)
        except SyncNotConfigured as exc:
            return _bad_request(str(exc))
        except ga4.GA4Error as exc:
            record_sync(GA4_PROVIDER, error=str(exc))
            return _upstream_error(str(exc))

        stored = record_sync(GA4_PROVIDER)
        payload = result.as_dict()
        payload["last_synced_at"] = timezone.now().isoformat() if stored is not None else None
        return Response(payload)


# --------------------------------------------------------------------------- #
# Instagram audience research (comments on public posts)
# --------------------------------------------------------------------------- #


def _instagram_enabled() -> bool:
    return bool(getattr(settings, "INSTAGRAM_SCRAPER_ENABLED", True))


class InstagramPostViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Tracked public posts. Adding one is offline; scraping needs the session."""

    serializer_class = InstagramTrackedPostSerializer
    permission_classes = [IsAuthenticated]
    ordering_fields = ["created_at", "last_scraped_at", "comment_count"]

    def get_queryset(self):
        return InstagramTrackedPost.objects.annotate(comments_stored=Count("comments"))

    def create(self, request, *args, **kwargs):
        payload = request.data if isinstance(request.data, dict) else {}
        url = (payload.get("url") or "").strip()
        if not url:
            return _bad_request("url is required.")
        try:
            post, created = resolve_post(url)
        except ValueError as exc:
            return _bad_request(str(exc))
        # Re-read through the annotated queryset so the payload always carries
        # comments_stored, exactly like list/retrieve.
        post = self.get_queryset().get(pk=post.pk)
        serializer = self.get_serializer(post)
        return Response(serializer.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    @action(detail=True, methods=["post"], permission_classes=[IsAdminUser])
    def scrape(self, request, pk=None):
        """Fetch comments for one tracked post (staff only)."""
        if not _instagram_enabled():
            return _bad_request("Instagram research is disabled (INSTAGRAM_SCRAPER_ENABLED).")
        post = self.get_object()
        payload = request.data if isinstance(request.data, dict) else {}
        raw_amount = payload.get("amount")
        if raw_amount in (None, ""):
            amount = None
        else:
            try:
                amount = int(raw_amount)
            except (TypeError, ValueError):
                return _bad_request("amount must be an integer.")
            if amount < 1:
                return _bad_request("amount must be at least 1.")

        try:
            result = sync_post(post, amount=amount)
        except InstagramNotConfigured as exc:
            return _bad_request(str(exc))
        except InstagramSessionInvalid as exc:
            record_sync(INSTAGRAM_PROVIDER, error=str(exc))
            mark_failed(post, exc)
            return _bad_request(str(exc))
        except InstagramRateLimited as exc:
            record_sync(INSTAGRAM_PROVIDER, error=str(exc))
            mark_failed(post, exc)
            return _rate_limited(str(exc))
        except InstagramError as exc:
            record_sync(INSTAGRAM_PROVIDER, error=str(exc))
            mark_failed(post, exc)
            return _upstream_error(str(exc))

        record_sync(INSTAGRAM_PROVIDER)
        payload_out = result.as_dict()
        payload_out["post"] = self.get_serializer(post).data
        return Response(payload_out)


class InstagramCommentListView(ListAPIView):
    """Stored comments, filterable by post and searchable by author/text."""

    serializer_class = InstagramCommentSerializer
    permission_classes = [IsAuthenticated]
    queryset = InstagramComment.objects.select_related("post").all()
    filterset_fields = ["post", "author_username"]
    search_fields = ["author_username", "author_full_name", "text"]
    ordering_fields = ["commented_at", "like_count", "fetched_at"]
    ordering = ["-commented_at", "-fetched_at"]


class InstagramAnalysisView(APIView):
    """Who keeps showing up: top commenters, repeat commenters, per-post totals."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        params = request.query_params
        queryset = InstagramComment.objects.all()
        post_id = _campaign_id(params.get("post"))
        if post_id:
            queryset = queryset.filter(post_id=post_id)

        by_author = list(
            queryset.values("author_username")
            .annotate(comments=Count("id"), posts=Count("post", distinct=True))
            .order_by("-comments", "author_username")
        )
        repeat = sorted(
            [row for row in by_author if row["comments"] > 1],
            key=lambda row: (-row["comments"], row["author_username"]),
        )

        posts = InstagramTrackedPost.objects.annotate(comments_stored=Count("comments"))
        if post_id:
            posts = posts.filter(pk=post_id)

        return Response(
            {
                "totals": {
                    "comments": queryset.count(),
                    "commenters": len(by_author),
                    "repeat_commenters": len(repeat),
                    "posts": posts.count(),
                },
                "top_commenters": by_author[:25],
                "repeat_commenters": repeat[:25],
                "by_post": [
                    {
                        "id": post.id,
                        "shortcode": post.shortcode,
                        "owner_username": post.owner_username,
                        "stored": post.comments_stored,
                        "reported": post.comment_count,
                        "last_scraped_at": post.last_scraped_at,
                    }
                    for post in posts
                ],
            }
        )


class InstagramExportView(APIView):
    """CSV of the stored comments, honouring the same filters as the list."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = InstagramComment.objects.select_related("post").all()
        params = request.query_params
        post_id = _campaign_id(params.get("post"))
        if post_id:
            queryset = queryset.filter(post_id=post_id)
        if params.get("author_username"):
            queryset = queryset.filter(author_username=params["author_username"])
        if params.get("search"):
            term = params["search"]
            queryset = queryset.filter(author_username__icontains=term) | queryset.filter(text__icontains=term)

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="instagram-comments.csv"'
        writer = csv.writer(response)
        writer.writerow(
            [
                "post_shortcode", "author_username", "author_full_name",
                "text", "commented_at", "like_count", "child_count", "fetched_at",
            ]
        )
        for comment in queryset.order_by("-commented_at", "-fetched_at")[:10000]:
            writer.writerow(
                [
                    comment.post.shortcode,
                    comment.author_username,
                    comment.author_full_name,
                    comment.text,
                    comment.commented_at.isoformat() if comment.commented_at else "",
                    comment.like_count,
                    comment.child_count,
                    comment.fetched_at.isoformat() if comment.fetched_at else "",
                ]
            )
        return response


class InstagramTestView(APIView):
    """Validate the stored sessionid and report which account it belongs to."""

    permission_classes = [IsAdminUser]

    def post(self, request):
        if not _instagram_enabled():
            return _bad_request("Instagram research is disabled (INSTAGRAM_SCRAPER_ENABLED).")
        try:
            client = get_client()
        except InstagramNotConfigured as exc:
            return _bad_request(str(exc))
        try:
            username = client.validate()
        except InstagramSessionInvalid as exc:
            record_sync(INSTAGRAM_PROVIDER, error=str(exc))
            return _bad_request(str(exc))
        except InstagramError as exc:
            record_sync(INSTAGRAM_PROVIDER, error=str(exc))
            return _upstream_error(str(exc))
        record_sync(INSTAGRAM_PROVIDER)
        return Response({"ok": True, "username": username})
