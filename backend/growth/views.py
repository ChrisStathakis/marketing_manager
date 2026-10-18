"""API for the organic-growth tools.

Read-heavy by design: the public site is the source of truth, this app shapes
its numbers into cards and captions, and a person decides what gets published.
"""

from __future__ import annotations

from datetime import date, timedelta

from django.conf import settings
from django.core.files.base import ContentFile
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from campaigns.models import Campaign
from channels.models import Channel
from content.serializers import ContentItemSerializer
from google_sync import ga4
from google_sync.services import PROVIDER as GA4_PROVIDER
from google_sync.services import SyncNotConfigured
from integrations.services import credential_status, record_sync

from . import analytics
from . import traffic as traffic_service
from .builders import build_spec, display_name
from .captions import FULL_LOCALES, LOCALES, PLATFORMS, build_captions
from .cards import SIZES, render_card
from .datasource import (
    COUNTRY_LABELS,
    PRIORITY_TEAMS,
    CatchAndStatsClient,
    DatasourceError,
    season_table,
    search_players,
)
from .insights import KIND_LABELS, build_insights
from .metrics import METRICS, metric_label
from .models import GrowthExperiment, PostPerformance, StatCard, TrafficSnapshot
from .planning import build_plan, seed_plan, site_link
from .serializers import (
    GrowthExperimentSerializer,
    PostPerformanceSerializer,
    StatCardSerializer,
    TrafficSnapshotSerializer,
)
from .sources import SOURCE_PLATFORMS

PLATFORM_LABELS = dict(PostPerformance.PLATFORM_CHOICES)
MAX_DAYS = 365


def _bad_request(message: str) -> Response:
    return Response({"detail": message}, status=status.HTTP_400_BAD_REQUEST)


def _upstream_error(message: str) -> Response:
    return Response({"detail": message}, status=status.HTTP_502_BAD_GATEWAY)


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
    table = season_table(payload.get("season"), refresh=bool(payload.get("refresh")))
    teams = payload.get("teams")
    if isinstance(teams, str):
        teams = [item for item in teams.split(",") if item]
    return build_spec(
        table,
        payload.get("kind") or "metric",
        player_id=payload.get("player"),
        opponent_id=payload.get("opponent"),
        metric=payload.get("metric"),
        country=payload.get("country") or None,
        story=payload.get("story") or None,
        teams=teams,
        title=payload.get("title") or None,
    )


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
                "sizes": SIZES,
                "platforms": [choice for choice in PostPerformance.PLATFORM_CHOICES if choice[0] in PLATFORMS],
                "log_platforms": PostPerformance.PLATFORM_CHOICES,
                "locales": LOCALES,
                "full_locales": sorted(FULL_LOCALES),
                "metrics": [
                    {"key": key, "label": metric.label, "short": metric.short, "digits": metric.digits}
                    for key, metric in METRICS.items()
                ],
                "site_url": _site_url(),
                "sources": SOURCE_PLATFORMS,
                "ga4_configured": credential_status(GA4_PROVIDER)["configured"],
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


class GrowthSuggestView(APIView):
    """Auto-pick the next post: the data chooses, the editor approves."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        params = request.query_params
        platform = params.get("platform") or "x"
        utm_campaign = params.get("utm_campaign") or "organic-growth"
        try:
            table = season_table(params.get("season"))
            spec = build_spec(
                table,
                params.get("kind") or "metric",
                player_id=params.get("player"),
                opponent_id=params.get("opponent"),
                metric=params.get("metric"),
                country=params.get("country") or None,
                story=params.get("story") or None,
                teams=[item for item in (params.get("teams") or "").split(",") if item],
                title=params.get("title") or None,
            )
        except DatasourceError as exc:
            return _upstream_error(str(exc))
        except ValueError as exc:
            return _bad_request(str(exc))
        return Response(
            {
                "spec": spec,
                **_table_meta(table),
                "link": site_link(_site_url(), platform, utm_campaign),
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
    filterset_fields = ["kind", "format", "campaign"]
    ordering_fields = ["created_at"]

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
        link = payload.get("link") or site_link(_site_url(), payload.get("platform") or "x", "organic-growth")
        drafts = build_captions(
            card.payload,
            link=link,
            platforms=payload.get("platforms"),
            locales=payload.get("locales"),
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
        if link:
            links: dict[str, str] = {}
        else:
            # Reddit gets no tracked URL by default: a naked UTM link in a text
            # post reads like an ad and trips the self-promotion rules.
            links = {
                platform: site_link(_site_url(), platform, utm_campaign)
                for platform in PLATFORMS
                if platform != "reddit"
            }
            link = site_link(_site_url(), "x", utm_campaign)
        drafts = build_captions(
            spec,
            link=link,
            platforms=payload.get("platforms") or PLATFORMS,
            locales=payload.get("locales") or LOCALES,
            links=links,
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


class PostPerformanceViewSet(viewsets.ModelViewSet):
    queryset = PostPerformance.objects.select_related("campaign", "content_item").all()
    serializer_class = PostPerformanceSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["platform", "campaign", "content_item"]
    search_fields = ["notes", "url"]
    ordering_fields = ["posted_at", "impressions", "engagements", "clicks", "created_at"]


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
        snapshots = list(TrafficSnapshot.objects.filter(date__gte=day - timedelta(days=days)))

        return Response(
            {
                "days": days,
                "since": since,
                "previous_since": previous_since,
                "totals": analytics.group_stats(current),
                "previous_totals": analytics.group_stats(previous),
                "by_platform": by_platform,
                "by_kind": analytics.flatten(analytics.group_by(current, "kind", KIND_LABELS), "kind"),
                "by_metric": analytics.flatten(analytics.group_by(current, "metric_key", metric_labels), "metric"),
                "trend": analytics.platform_trend(current, previous, PLATFORM_LABELS),
                "traffic": analytics.traffic_summary(snapshots, PLATFORM_LABELS),
                "traffic_configured": credential_status(GA4_PROVIDER)["configured"],
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
