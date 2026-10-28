import io
import json
import os
import shutil
import tempfile
import time
import urllib.error
from datetime import date, timedelta
from types import SimpleNamespace
from unittest import mock
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, override_settings
from django.utils import timezone
from PIL import Image
from rest_framework.test import APITestCase

from campaigns.models import Campaign
from channels.models import Channel
from content.models import ContentItem
from google_sync import ga4
from growth.analytics import flatten, group_by, group_stats
from growth.builders import build_spec, build_team_card, build_top8_table, team_short
from growth.cards import SIZES, render_card
from growth.captions import build_captions
from growth.datasource import CACHE_VERSION, CatchAndStatsClient, DatasourceError, cache_dir, priority_country, _write_cache
from growth.insights import build_insights
from growth.instagram import (
    FetchedComment,
    InstagramClient,
    InstagramNotConfigured,
    InstagramRateLimited,
    InstagramSessionInvalid,
    media_pk_from_shortcode,
    shortcode_from_url,
)
from growth.instagram_service import CommentSyncResult, sync_post
from growth.metrics import format_metric
from growth.models import (
    Boost,
    CardSet,
    GrowthExperiment,
    InstagramComment,
    InstagramTrackedPost,
    KpiTarget,
    Playbook,
    PlaybookSlot,
    PostPerformance,
    SearchConsoleSnapshot,
    StatCard,
    TrafficSnapshot,
)
from growth.planning import site_link
from growth.search_console import SearchConsoleResult, build_report, sync_search_console
from growth.sources import platform_for_source
from growth.traffic import TrafficResult, sync_organic
from plans.models import Task

#: Minimal season reference row, shared by the datasource tests.
SEASON_ROW = {"id": 6, "season_id": "E2026", "title": "2026-2027", "default_season": True}


def player(pid, name, team, country, **overrides):
    metrics = {
        "games": 6,
        "time_played": 22.0,
        "score": 10.0,
        "ts_pct": 0.55,
        "usage_pct": 20.0,
        "per": 12.0,
        "consistency_score": 55.0,
        "home_court_advantage": 5.0,
        "fantasy_points_ceiling": 20.0,
        "net_rating": 3.0,
        "ast_to_ratio": 1.5,
    }
    metrics.update(overrides)
    return {
        "id": pid,
        "player_id": pid,
        "player": name,
        "team": team,
        "season": "2026-2027",
        "season_id": "E2026",
        "position": "Forward",
        "country": country,
        "metrics": metrics,
    }


TABLE = {
    "season": {"id": 6, "season_id": "E2026", "title": "2026-2027"},
    "players": [
        player(1, "VEZENKOV, SASHA", "Olympiacos Piraeus", "GR", score=18.4, ts_pct=0.62, usage_pct=26.0),
        player(2, "NUNN, KENDRICK", "Panathinaikos AKTOR Athens", "GR", score=17.2, ts_pct=0.58, usage_pct=28.0),
        player(3, "JOKUBO, ROKAS", "Zalgiris Kaunas", "LT", score=14.1, ts_pct=0.51, usage_pct=24.0),
        player(4, "PETRUSEV, FILIP", "Partizan Mozzart Bet Belgrade", "RS", score=15.8, ts_pct=0.61, usage_pct=22.0),
        # An artefact that must never top a card.
        player(5, "CAMEOS, TWO", "Besiktas Istanbul", "TR", games=1, time_played=2.0, ts_pct=1.5),
    ],
    "teams": [
        {
            "id": 1,
            "team_title": "Olympiacos Piraeus",
            "season_title": "2026-2027",
            "offensive_rating": 120.8,
            "defensive_rating": 109.7,
            "avg_pace": 78.3,
            "team_average_fantasy_points": 19.9,
        },
        {
            "id": 2,
            "team_title": "Panathinaikos AKTOR Athens",
            "season_title": "2026-2027",
            "offensive_rating": 116.9,
            "defensive_rating": 98.6,
            "avg_pace": 74.7,
            "team_average_fantasy_points": 17.7,
        },
    ],
    "fetched_at": "2026-10-18T10:00:00+00:00",
    "source": "https://catchandstats.com/api",
}


class MediaIsolationMixin:
    @classmethod
    def setUpClass(cls):
        cls._media = tempfile.mkdtemp(prefix="growth-media-")
        cls._override = override_settings(MEDIA_ROOT=cls._media)
        cls._override.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._override.disable()
        shutil.rmtree(cls._media, ignore_errors=True)


class GrowthApiTests(MediaIsolationMixin, APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="growth", password="x")
        cls.campaign = Campaign.objects.create(name="EuroLeague organic", utm_campaign="euroleague-organic")
        for channel_type in ("x", "instagram", "reddit", "tiktok", "telegram"):
            Channel.objects.create(name=channel_type.title(), channel_type=channel_type)

    def setUp(self):
        self.client.force_authenticate(user=self.user)

    def test_meta_requires_authentication(self):
        self.client.force_authenticate(user=None)
        response = self.client.get("/api/growth/meta/")
        self.assertEqual(response.status_code, 401)

    @patch("growth.views.CatchAndStatsClient")
    def test_meta_lists_formats_and_markets(self, mock_client):
        instance = mock_client.return_value
        instance.seasons.return_value = [{"id": 6, "season_id": "E2026", "title": "2026-2027", "default_season": True}]
        instance.warnings = []
        response = self.client.get("/api/growth/meta/")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["default_season"]["season_id"], "E2026")
        self.assertTrue({"player", "metric", "matchup"} <= {kind[0] for kind in body["kinds"]})
        self.assertEqual(set(body["sizes"]), set(SIZES))
        self.assertIn("GR", body["priority_teams"])
        self.assertIn("el", body["locales"])
        self.assertIn("tiktok", body["sources"].values())
        self.assertIn("can_sync", body)

    @patch("growth.views.CatchAndStatsClient")
    def test_meta_survives_upstream_failure(self, mock_client):
        mock_client.return_value.seasons.side_effect = DatasourceError("offline")
        mock_client.return_value.warnings = []
        response = self.client.get("/api/growth/meta/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["seasons"], [])
        self.assertIn("offline", response.json()["warning"])

    @patch("growth.views.CatchAndStatsClient")
    def test_meta_reports_stale_upstream_reads(self, mock_client):
        mock_client.return_value.seasons.return_value = [{"id": 6, "title": "2026-2027", "default_season": True}]
        mock_client.return_value.warnings = ["the season list came from the cache"]
        response = self.client.get("/api/growth/meta/")
        self.assertIn("cache", response.json()["warning"])

    @patch("growth.views.season_table")
    def test_players_are_ordered_by_descending_metric(self, mock_table):
        mock_table.return_value = TABLE
        response = self.client.get("/api/growth/players/?country=GR&ordering=-score")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        scores = [row["metrics"]["score"] for row in body["results"]]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertEqual(body["results"][0]["name"], "Sasha Vezenkov")
        self.assertIn("Panathinaikos AKTOR Athens", body["teams"])

    @patch("growth.views.season_table")
    def test_suggest_builds_a_metric_card(self, mock_table):
        mock_table.return_value = TABLE
        response = self.client.get("/api/growth/suggest/?kind=metric&story=ts_pct")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["spec"]["kind"], "metric")
        # The 150% cameo is filtered out; the best plausible shooter leads.
        self.assertEqual(body["spec"]["subtitle"].split(" · ")[0], "Sasha Vezenkov")
        self.assertIn("utm_source=x", body["link"])

    @patch("growth.views.season_table")
    def test_suggest_rejects_unknown_metric(self, mock_table):
        mock_table.return_value = TABLE
        response = self.client.get("/api/growth/suggest/?kind=metric&story=not_a_metric")
        self.assertEqual(response.status_code, 400)

    @patch("growth.views.season_table")
    def test_preview_returns_a_png(self, mock_table):
        mock_table.return_value = TABLE
        response = self.client.post(
            "/api/growth/cards/preview/",
            {"kind": "round_recap", "format": "x"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/png")
        self.assertTrue(response.content.startswith(b"\x89PNG"))

    def test_preview_rejects_unknown_format(self):
        response = self.client.post("/api/growth/cards/preview/", {"format": "billboard"}, format="json")
        self.assertEqual(response.status_code, 400)

    @patch("growth.views.season_table")
    def test_saving_a_card_writes_the_image(self, mock_table):
        mock_table.return_value = TABLE
        response = self.client.post(
            "/api/cards/",
            {"kind": "player", "format": "instagram", "campaign": self.campaign.id},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        card = StatCard.objects.get()
        self.assertEqual(card.format, "instagram")
        self.assertTrue(card.image.name.endswith(".png"))
        self.assertTrue(card.image.path.startswith(self._media))
        self.assertIn("image_url", response.json())

    @patch("growth.views.season_table")
    def test_captions_cover_every_language_and_fit_x(self, mock_table):
        mock_table.return_value = TABLE
        response = self.client.post("/api/growth/captions/", {"kind": "comparison"}, format="json")
        self.assertEqual(response.status_code, 200)
        drafts = response.json()["drafts"]
        self.assertEqual({draft["locale"] for draft in drafts}, {"en", "el", "tr", "sr", "lt"})
        x_drafts = [draft for draft in drafts if draft["platform"] == "x"]
        self.assertEqual(len(x_drafts), 5)
        self.assertTrue(all(draft["within_limit"] for draft in x_drafts))
        reddit = next(draft for draft in drafts if draft["platform"] == "reddit")
        self.assertTrue(reddit["title"])
        self.assertIn("catchandstats.com", reddit["text"])

    @patch("growth.views.season_table")
    def test_plan_seeds_a_week_once(self, mock_table):
        mock_table.return_value = TABLE
        payload = {
            "campaign": self.campaign.id,
            "round_label": "Round 6",
            "start_date": "2026-10-21",  # Wednesday; should snap to Monday
            "season": "E2026",
        }
        first = self.client.post("/api/growth/plan/", payload, format="json")
        self.assertEqual(first.status_code, 201)
        self.assertEqual(first.json()["created"], 8)
        self.assertEqual(first.json()["week_start"], "2026-10-19")
        self.assertEqual(ContentItem.objects.count(), 8)
        self.assertEqual(Task.objects.count(), 8)
        self.assertEqual(first.json()["missing_channels"], [])

        second = self.client.post("/api/growth/plan/", payload, format="json")
        self.assertEqual(second.status_code, 201)
        self.assertEqual(second.json()["created"], 0)
        self.assertEqual(second.json()["skipped"], 8)
        self.assertEqual(ContentItem.objects.count(), 8)

    def test_report_totals_and_ranking(self):
        now = timezone.now()
        PostPerformance.objects.create(
            platform="x", impressions=1000, engagements=40, clicks=60, posted_at=now - timedelta(days=2)
        )
        PostPerformance.objects.create(
            platform="reddit", impressions=5000, engagements=250, clicks=100, posted_at=now - timedelta(days=1)
        )
        response = self.client.get("/api/growth/report/?days=30")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["totals"]["posts"], 2)
        self.assertEqual(body["totals"]["clicks"], 160)
        # Ranked by click rate, not raw volume: X converts better here.
        self.assertEqual(body["by_platform"][0]["platform"], "x")
        self.assertAlmostEqual(body["by_platform"][0]["click_rate"], 0.06)
        self.assertAlmostEqual(body["by_platform"][1]["click_rate"], 0.02)

    def test_report_breaks_down_kind_metric_and_trend(self):
        now = timezone.now()
        PostPerformance.objects.create(
            platform="x", kind="metric", metric_key="consistency_score",
            impressions=1000, engagements=40, clicks=60, posted_at=now - timedelta(days=2),
        )
        PostPerformance.objects.create(
            platform="x", kind="metric", metric_key="consistency_score",
            impressions=1000, engagements=10, clicks=10, posted_at=now - timedelta(days=40),
        )
        body = self.client.get("/api/growth/report/?days=30").json()
        self.assertEqual([row["metric"] for row in body["by_metric"]], ["consistency_score"])
        self.assertEqual(body["by_metric"][0]["label"], "Consistency score")
        self.assertEqual(body["by_kind"][0]["kind"], "metric")
        self.assertEqual(body["by_kind"][0]["posts"], 1)
        trend = next(row for row in body["trend"] if row["platform"] == "x")
        self.assertEqual(trend["direction"], "up")
        self.assertAlmostEqual(trend["delta_click_rate"], 0.05)
        self.assertIn("traffic", body)
        self.assertEqual(body["previous_totals"]["posts"], 1)

    def test_report_ignores_an_unknown_campaign_filter(self):
        response = self.client.get("/api/growth/report/?days=30&campaign=not-a-number")
        self.assertEqual(response.status_code, 200)

    @patch("growth.views.search_console_service.build_report")
    def test_report_uses_search_console_for_kpi_actuals(self, mock_search):
        KpiTarget.objects.create(campaign=self.campaign, metric="search_clicks", target=20)
        mock_search.return_value = {
            "totals": {"clicks": 15, "impressions": 150, "ctr": 0.1},
            "campaign": {"totals": {"clicks": 15, "impressions": 150, "ctr": 0.1}},
        }
        body = self.client.get(
            f"/api/growth/report/?days=30&campaign={self.campaign.id}"
        ).json()
        row = next(item for item in body["kpi_targets"] if item["metric"] == "search_clicks")
        self.assertEqual(row["actual"], 15)
        self.assertAlmostEqual(row["progress"], 0.75)
        self.assertIn("search_console", body)

    def test_site_link_keeps_utm_parameters(self):
        link = site_link("https://catchandstats.com", "reddit", "euroleague-organic")
        self.assertEqual(
            link,
            "https://catchandstats.com/?utm_source=reddit&utm_medium=social&utm_campaign=euroleague-organic",
        )

    def test_site_link_can_target_a_landing_path(self):
        link = site_link(
            "https://catchandstats.com/",
            "x",
            "top8",
            "thread_en",
            path="team-advanced-stats/",
        )
        self.assertEqual(
            link,
            "https://catchandstats.com/team-advanced-stats?utm_source=x&utm_medium=social&utm_campaign=top8&utm_content=thread_en",
        )


class GrowthUnitTests(SimpleTestCase):
    def test_priority_markets_match_sponsored_names(self):
        self.assertEqual(priority_country("Panathinaikos AKTOR Athens"), "GR")
        self.assertEqual(priority_country("Fenerbahce Tarfin Istanbul"), "TR")
        self.assertEqual(priority_country("Crvena Zvezda Meridianbet Belgrade"), "RS")
        self.assertEqual(priority_country("Zalgiris Kaunas"), "LT")
        self.assertIsNone(priority_country("Real Madrid"))

    def test_priority_markets_do_not_match_mid_word(self):
        # "aris" must not claim Paris, and "aek" must not claim a random name.
        self.assertIsNone(priority_country("Paris Basketball"))
        self.assertIsNone(priority_country("Hapoel IBI Tel Aviv"))
        self.assertEqual(priority_country("Aris Thessaloniki"), "GR")

    def test_season_resolution_accepts_id_code_or_title(self):
        seasons = [{"id": 6, "season_id": "E2026", "title": "2026-2027", "default_season": True}]
        self.assertEqual(CatchAndStatsClient.resolve_season(seasons, "E2026")["id"], 6)
        self.assertEqual(CatchAndStatsClient.resolve_season(seasons, "2026-2027")["id"], 6)
        self.assertEqual(CatchAndStatsClient.resolve_season(seasons, None)["id"], 6)

    def test_percentage_units_and_artefacts(self):
        self.assertEqual(format_metric("ts_pct", 0.6069), "60.7%")
        self.assertEqual(format_metric("usage_pct", 25.32), "25.3%")
        self.assertEqual(format_metric("ts_pct", 1.5), "—")
        self.assertEqual(format_metric("score", None), "—")

    def test_builder_skips_cameos(self):
        spec = build_spec(TABLE, "metric", story="ts_pct")
        self.assertEqual(spec["title"], "True shooting")
        self.assertIn("Vezenkov", spec["subtitle"])
        self.assertNotIn("Cameos", spec["subtitle"])

    def test_team_short_names_drop_sponsors(self):
        self.assertEqual(team_short("Panathinaikos AKTOR Athens"), "Panathinaikos")
        self.assertEqual(team_short("Fenerbahce Tarfin Istanbul"), "Fenerbahçe")
        self.assertEqual(team_short("Crvena Zvezda Meridianbet Belgrade"), "Crvena Zvezda")

    def test_captions_keep_the_x_budget(self):
        spec = build_spec(TABLE, "round_recap")
        drafts = build_captions(spec, link="https://catchandstats.com/?utm_source=x", platforms=["x"])
        self.assertTrue(drafts)
        for draft in drafts:
            self.assertLessEqual(len(draft["text"]), 280)

    def test_renderer_handles_every_size(self):
        spec = build_spec(TABLE, "comparison")
        for fmt, (width, height) in SIZES.items():
            png = render_card(spec, fmt)
            self.assertTrue(png.startswith(b"\x89PNG"), fmt)
            with Image.open(io.BytesIO(png)) as image:
                self.assertEqual(image.size, (width, height), fmt)

    def test_sources_map_to_platforms(self):
        self.assertEqual(platform_for_source("x"), "x")
        self.assertEqual(platform_for_source("www.reddit.com"), "reddit")
        self.assertEqual(platform_for_source("l.instagram.com"), "instagram")
        self.assertEqual(platform_for_source("t.co"), "x")
        self.assertIsNone(platform_for_source("google"))
        self.assertIsNone(platform_for_source(None))

    def test_analytics_flatten_and_group_stats(self):
        posts = [
            SimpleNamespace(impressions=1000, engagements=40, comments=2, clicks=60, platform="x", kind="metric", metric_key="ts_pct"),
            SimpleNamespace(impressions=1000, engagements=10, comments=0, clicks=10, platform="x", kind="metric", metric_key="ts_pct"),
        ]
        self.assertAlmostEqual(group_stats(posts)["click_rate"], 0.035)
        self.assertAlmostEqual(group_stats(posts)["engagement_rate"], 0.025)
        rows = flatten(group_by(posts, "platform"), "platform")
        self.assertEqual(rows[0]["platform"], "x")
        self.assertEqual(rows[0]["posts"], 2)
        self.assertAlmostEqual(rows[0]["click_rate"], 0.035)


class GrowthInsightRuleTests(APITestCase):
    """The rules are the product here, so they get real fixtures."""

    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="insights", password="x")

    def setUp(self):
        self.client.force_authenticate(user=self.user)

    def _post(self, platform, impressions, clicks, days_ago=1, **kwargs):
        PostPerformance.objects.create(
            platform=platform,
            impressions=impressions,
            engagements=clicks * 2,
            clicks=clicks,
            posted_at=timezone.now() - timedelta(days=days_ago),
            **kwargs,
        )

    def insights(self):
        response = self.client.get("/api/growth/insights/")
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def test_empty_state_points_at_the_first_post(self):
        body = self.insights()
        self.assertEqual([entry["id"] for entry in body["insights"]], ["no-data"])
        self.assertEqual(body["insights"][0]["severity"], "info")
        self.assertEqual(body["next_cards"][0]["kind"], "round_recap")

    def test_best_platform_rule_prefers_click_rate(self):
        for _ in range(4):
            self._post("x", 1000, 60)
            self._post("reddit", 5000, 50)
        best = next(entry for entry in self.insights()["insights"] if entry["id"] == "best-platform")
        self.assertIn("X / Twitter", best["title"])
        self.assertEqual(best["severity"], "win")
        self.assertTrue(any("Reddit" in line for line in best["evidence"]))

    def test_single_platform_is_not_ranked(self):
        self._post("x", 1000, 60)
        ids = {entry["id"] for entry in self.insights()["insights"]}
        self.assertNotIn("best-platform", ids)

    def test_clicks_without_traffic_are_flagged(self):
        self._post("x", 1000, 10)
        TrafficSnapshot.objects.create(
            date=timezone.localdate(), source="reddit.com", medium="referral", sessions=200, engaged_sessions=120
        )
        ids = {entry["id"] for entry in self.insights()["insights"]}
        self.assertIn("traffic-leak", ids)
        self.assertIn("unlogged-traffic", ids)

    def test_best_metric_rule_drives_the_next_card(self):
        for _ in range(2):
            self._post("x", 1000, 80, metric_key="consistency_score", kind="metric")
            self._post("x", 1000, 20, metric_key="ts_pct", kind="metric")
        body = self.insights()
        best = next(entry for entry in body["insights"] if entry["id"] == "best-metric")
        self.assertIn("Consistency score", best["title"])
        self.assertEqual(best["action"]["metric"], "consistency_score")
        self.assertEqual(body["next_cards"][0]["metric"], "consistency_score")
        # The metric card is a "metric" card, so the kind leader must not repeat it.
        self.assertEqual(len(body["next_cards"]), 1)

    def test_kind_leader_becomes_its_own_card(self):
        for _ in range(2):
            self._post("x", 1000, 90, kind="round_recap")
            self._post("x", 1000, 10, kind="player")
        body = self.insights()
        self.assertEqual(body["next_cards"][0]["kind"], "round_recap")
        self.assertIsNone(body["next_cards"][0]["metric"])

    def test_reach_without_clicks_is_flagged(self):
        self._post("x", 1000, 100, days_ago=2)     # 10% click rate
        self._post("x", 1000, 100, days_ago=3)
        self._post("x", 9000, 20, days_ago=4)      # far reach, poor conversion
        ids = {entry["id"] for entry in self.insights()["insights"]}
        self.assertIn("reach-without-clicks", ids)

    def test_stale_experiment_and_idea_backlog_are_flagged(self):
        GrowthExperiment.objects.create(
            name="Threads vs single post", status="running", started_on=timezone.localdate() - timedelta(days=40)
        )
        for index in range(3):
            GrowthExperiment.objects.create(name=f"Idea {index}", status="idea")
        ids = {entry["id"] for entry in self.insights()["insights"]}
        self.assertIn("stale-experiments", ids)
        self.assertIn("idea-backlog", ids)

    def test_insights_are_ordered_problems_first(self):
        self._post("x", 1000, 10)
        self._post("reddit", 5000, 200)
        TrafficSnapshot.objects.create(date=timezone.localdate(), source="reddit.com", medium="referral", sessions=90)
        severities = [entry["severity"] for entry in self.insights()["insights"]]
        self.assertEqual(severities, sorted(severities, key=["warn", "win", "info"].index))


class GrowthTrafficTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.admin = user_model.objects.create_user(username="traffic-admin", password="x", is_staff=True)
        cls.user = user_model.objects.create_user(username="traffic-user", password="x")

    def test_parse_traffic_report_keeps_direct_traffic(self):
        payload = {
            "rows": [
                {
                    "dimensionValues": [{"value": "20261010"}, {"value": "x"}, {"value": "social"}],
                    "metricValues": [{"value": "120"}, {"value": "80"}, {"value": "100"}, {"value": "300"}],
                },
                {
                    "dimensionValues": [{"value": "20261011"}, {"value": ""}, {"value": ""}],
                    "metricValues": [{"value": "5"}, {"value": "1"}, {"value": "5"}, {"value": "6"}],
                },
                {
                    "dimensionValues": [{"value": "nope"}, {"value": "x"}, {"value": "social"}],
                    "metricValues": [{"value": "1"}] * 4,
                },
            ]
        }
        rows = ga4.parse_traffic_report(payload)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["sessions"], 120)
        self.assertEqual(rows[0]["engaged_sessions"], 80)
        self.assertEqual(rows[0]["users"], 100)
        self.assertEqual(rows[0]["views"], 300)
        self.assertEqual(rows[1]["source"], "(direct)")

    def test_fetch_traffic_daily_requests_the_traffic_dimensions(self):
        captured = {}

        class Fake:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def read(self):
                return json.dumps({"rows": []}).encode()

        def fake_urlopen(request, timeout=None):
            captured["body"] = json.loads(request.data.decode())
            captured["auth"] = request.headers.get("Authorization")
            return Fake()

        with mock.patch("google_sync.ga4._access_token", return_value="tok"), mock.patch(
            "urllib.request.urlopen", side_effect=fake_urlopen
        ):
            ga4.fetch_traffic_daily("{}", "123", date(2026, 10, 1), date(2026, 10, 7))

        self.assertEqual(
            [dimension["name"] for dimension in captured["body"]["dimensions"]],
            ["date", "sessionSource", "sessionMedium", "sessionCampaignName", "sessionManualAdContent"],
        )
        self.assertEqual(
            captured["body"]["dateRanges"], [{"startDate": "2026-10-01", "endDate": "2026-10-07"}]
        )
        self.assertEqual(captured["auth"], "Bearer tok")

    @mock.patch("growth.traffic.get_credential_config", return_value={"property_id": "1"})
    @mock.patch("growth.traffic.get_credential_value", return_value="{}")
    @mock.patch("growth.traffic.ga4.fetch_traffic_daily")
    def test_sync_organic_upserts_idempotently(self, mock_fetch, *_):
        mock_fetch.return_value = [
            {"date": "2026-10-10", "source": "x", "medium": "social", "sessions": 120, "engaged_sessions": 80, "users": 100, "views": 300},
            {"date": "2026-10-10", "source": "google", "medium": "organic", "sessions": 400, "engaged_sessions": 300, "users": 380, "views": 900},
        ]
        first = sync_organic(days=30)
        second = sync_organic(days=30)

        self.assertEqual((first.created, first.updated), (2, 0))
        self.assertEqual((second.created, second.updated), (0, 2))
        self.assertEqual(TrafficSnapshot.objects.count(), 2)
        self.assertEqual(first.sessions, 520)
        self.assertEqual(first.social_sessions, 120)
        self.assertEqual(first.other_sources, ["google"])

    def test_sync_organic_requires_credentials(self):
        from google_sync.services import SyncNotConfigured

        with mock.patch("growth.traffic.get_credential_value", return_value=None):
            with self.assertRaises(SyncNotConfigured):
                sync_organic(days=7)

    def test_traffic_sync_is_staff_only(self):
        self.client.force_authenticate(user=self.user)
        self.assertEqual(self.client.post("/api/growth/traffic/sync/").status_code, 403)

    def test_traffic_sync_rejects_bad_days(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post("/api/growth/traffic/sync/", {"days": 4000}, format="json")
        self.assertEqual(response.status_code, 400)

    @mock.patch("growth.views.traffic_service.sync_organic")
    def test_traffic_sync_endpoint_reports_counts(self, mock_sync):
        mock_sync.return_value = TrafficResult(
            created=3, rows=3, sessions=210, social_sessions=210, start="2026-09-18", end="2026-10-17"
        )
        self.client.force_authenticate(user=self.admin)
        response = self.client.post("/api/growth/traffic/sync/", {"days": 30}, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["created"], 3)
        self.assertEqual(response.json()["social_sessions"], 210)

    @mock.patch("growth.views.traffic_service.sync_organic")
    def test_traffic_sync_reports_google_failures(self, mock_sync):
        mock_sync.side_effect = ga4.GA4Error("GA4 API error 403: permission denied")
        self.client.force_authenticate(user=self.admin)
        response = self.client.post("/api/growth/traffic/sync/", {}, format="json")
        self.assertEqual(response.status_code, 502)
        self.assertIn("403", response.json()["detail"])

    @mock.patch("growth.traffic.sync_organic")
    @mock.patch("google_sync.management.commands.sync_google.sync_ga4")
    def test_sync_google_organic_flag_pulls_traffic(self, mock_ga4, mock_organic):
        from io import StringIO

        from django.core.management import call_command

        from google_sync.services import SyncResult

        mock_ga4.return_value = SyncResult(rows=3, start="2026-10-11", end="2026-10-17")
        mock_organic.return_value = TrafficResult(
            rows=2, sessions=500, social_sessions=210, start="2026-09-18", end="2026-10-17"
        )
        out = StringIO()
        call_command("sync_google", "--organic", stdout=out)

        mock_ga4.assert_called_once()
        mock_organic.assert_called_once()
        self.assertIn("GA4 organic", out.getvalue())
        self.assertIn("210", out.getvalue())

    @mock.patch("growth.traffic.sync_organic")
    @mock.patch("google_sync.management.commands.sync_google.sync_ga4")
    def test_sync_google_without_organic_skips_traffic(self, mock_ga4, mock_organic):
        from io import StringIO

        from django.core.management import call_command

        from google_sync.services import SyncResult

        mock_ga4.return_value = SyncResult(rows=1, start="2026-10-11", end="2026-10-17")
        call_command("sync_google", stdout=StringIO())
        mock_organic.assert_not_called()

    def test_traffic_endpoint_lists_snapshots_by_platform(self):
        TrafficSnapshot.objects.create(
            date=timezone.localdate(), source="x", medium="social", sessions=50, engaged_sessions=30
        )
        self.client.force_authenticate(user=self.user)
        body = self.client.get("/api/growth/traffic/").json()
        self.assertEqual(body["summary"]["totals"]["sessions"], 50)
        self.assertEqual(body["summary"]["by_platform"][0]["platform"], "x")
        self.assertEqual(body["results"][0]["platform"], "x")
        self.assertFalse(body["can_sync"])
        self.assertIsNotNone(body["last_synced_at"])


SITE_URL = "sc-domain:catchandstats.com"


class SearchConsoleTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="gsc-user", password="pw")
        self.admin = get_user_model().objects.create_user(
            username="gsc-admin", password="pw", is_staff=True
        )

    @mock.patch("growth.search_console.gsc.fetch_snapshot")
    @mock.patch("growth.search_console.get_credential_config", return_value={"site_url": SITE_URL})
    @mock.patch("growth.search_console.get_credential_value", return_value="{}")
    def test_sync_is_idempotent(self, _value, _config, mock_fetch):
        rows = [
            {
                "date": date(2026, 10, 10),
                "scope": "total",
                "page_url": "",
                "page_path": "",
                "query": "",
                "clicks": 12,
                "impressions": 300,
                "ctr": 0.04,
                "position": 4.2,
            },
            {
                "date": date(2026, 10, 10),
                "scope": "page",
                "page_url": "https://catchandstats.com/team/",
                "page_path": "/team",
                "query": "",
                "clicks": 10,
                "impressions": 200,
                "ctr": 0.05,
                "position": 3.0,
            },
            {
                "date": date(2026, 10, 10),
                "scope": "query",
                "page_url": "",
                "page_path": "",
                "query": "euroleague top 8",
                "clicks": 4,
                "impressions": 50,
                "ctr": 0.08,
                "position": 2.0,
            },
        ]
        mock_fetch.return_value = rows

        first = sync_search_console(days=7, today=date(2026, 10, 10))
        second = sync_search_console(days=7, today=date(2026, 10, 10))

        self.assertEqual((first.created, first.updated), (3, 0))
        self.assertEqual((second.created, second.updated), (0, 3))
        self.assertEqual(first.clicks, 12)
        self.assertEqual(first.impressions, 300)
        self.assertEqual(first.pages, 1)
        self.assertEqual(first.queries, 1)
        self.assertEqual(SearchConsoleSnapshot.objects.count(), 3)
        self.assertEqual(SearchConsoleSnapshot.objects.get(scope="page").page_path, "/team")

    def _campaign_with_link(self, link: str, name: str = "GSC campaign") -> Campaign:
        campaign = Campaign.objects.create(
            name=name,
            utm_campaign="gsc-campaign",
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 10),
        )
        ContentItem.objects.create(campaign=campaign, title="Post", link=link)
        return campaign

    @mock.patch("growth.search_console.credential_status", return_value={"configured": True})
    @mock.patch("growth.search_console.get_credential_config", return_value={"site_url": SITE_URL})
    def test_report_maps_campaign_through_linked_pages(self, _config, _status):
        campaign = self._campaign_with_link(
            "https://catchandstats.com/team/?utm_source=x&utm_campaign=gsc-campaign"
        )
        for path, clicks, impressions in (("/team", 20, 200), ("/other", 9, 90)):
            SearchConsoleSnapshot.objects.create(
                date=date(2026, 10, 5),
                site_url=SITE_URL,
                scope="page",
                page_url=f"https://catchandstats.com{path}",
                page_path=path,
                clicks=clicks,
                impressions=impressions,
                ctr=clicks / impressions,
                position=3.0,
            )

        report = build_report(campaign=campaign, today=date(2026, 10, 15))

        self.assertEqual(report["campaign"]["pages"], ["/team"])
        self.assertEqual(report["campaign"]["totals"]["clicks"], 20)
        self.assertEqual(report["campaign"]["totals"]["impressions"], 200)
        self.assertAlmostEqual(report["campaign"]["totals"]["ctr"], 0.1)
        self.assertEqual(report["campaign"]["by_page"][0]["page_path"], "/team")
        self.assertTrue(report["campaign"]["matched"])
        self.assertEqual(report["campaign"]["warning"], "")

    @mock.patch("growth.search_console.credential_status", return_value={"configured": True})
    @mock.patch("growth.search_console.get_credential_config", return_value={"site_url": SITE_URL})
    def test_report_warns_when_all_links_are_homepage(self, _config, _status):
        campaign = self._campaign_with_link("https://catchandstats.com/?utm_campaign=gsc-campaign")
        SearchConsoleSnapshot.objects.create(
            date=date(2026, 10, 5),
            site_url=SITE_URL,
            scope="page",
            page_url="https://catchandstats.com/",
            page_path="/",
            clicks=5,
            impressions=50,
            ctr=0.1,
            position=2.0,
        )

        report = build_report(campaign=campaign, today=date(2026, 10, 15))

        self.assertEqual(report["campaign"]["pages"], ["/"])
        self.assertIn("homepage", report["campaign"]["warning"])

    @mock.patch("growth.search_console.sync_search_console")
    def test_sync_endpoint_reports_the_snapshot(self, mock_sync):
        mock_sync.return_value = SearchConsoleResult(
            created=2,
            rows=2,
            pages=1,
            queries=1,
            clicks=11,
            impressions=100,
            start="2026-10-01",
            end="2026-10-10",
            site_url=SITE_URL,
        )
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            "/api/integrations/google-search-console/sync/", {"days": 7}, format="json"
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["clicks"], 11)
        self.assertEqual(response.json()["unmatched"], [])

    def test_sync_endpoint_requires_staff(self):
        self.client.force_authenticate(self.user)
        response = self.client.post("/api/integrations/google-search-console/sync/")
        self.assertEqual(response.status_code, 403)

    def test_report_endpoint_requires_authentication(self):
        self.assertEqual(self.client.get("/api/growth/search-console/").status_code, 401)


class DatasourceHardeningTests(SimpleTestCase):
    """The public API is remote and occasionally down; the studio must cope."""

    @classmethod
    def setUpClass(cls):
        cls._media = tempfile.mkdtemp(prefix="growth-cache-")
        cls._override = override_settings(MEDIA_ROOT=cls._media)
        cls._override.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._override.disable()
        shutil.rmtree(cls._media, ignore_errors=True)

    def setUp(self):
        for path in cache_dir().glob("*"):
            path.unlink()

    @staticmethod
    def _response(payload):
        class Fake:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def read(self):
                return json.dumps(payload).encode()

        return Fake()

    def test_transient_status_is_retried(self):
        calls = []

        def fake_urlopen(request, timeout=None):
            calls.append(request.full_url)
            if len(calls) == 1:
                raise urllib.error.HTTPError(request.full_url, 503, "busy", {}, None)
            return self._response({"ok": True})

        client = CatchAndStatsClient(base_url="https://example.test/api")
        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen), mock.patch(
            "growth.datasource.time.sleep"
        ) as sleep:
            payload = client.get("/thing/")
        self.assertEqual(payload, {"ok": True})
        self.assertEqual(len(calls), 2)
        sleep.assert_called_once()

    def test_client_errors_are_not_retried(self):
        calls = []

        def fake_urlopen(request, timeout=None):
            calls.append(request.full_url)
            raise urllib.error.HTTPError(request.full_url, 400, "bad season", {}, None)

        client = CatchAndStatsClient(base_url="https://example.test/api")
        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen), mock.patch("growth.datasource.time.sleep"):
            with self.assertRaises(DatasourceError) as caught:
                client.get("/thing/")
        self.assertEqual(len(calls), 1)
        self.assertEqual(caught.exception.status, 400)
        self.assertFalse(caught.exception.transient)

    def test_retry_after_header_is_respected(self):
        def fake_urlopen(request, timeout=None):
            raise urllib.error.HTTPError(request.full_url, 429, "slow down", {"Retry-After": "2"}, None)

        client = CatchAndStatsClient(base_url="https://example.test/api")
        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen), mock.patch(
            "growth.datasource.time.sleep"
        ) as sleep:
            with self.assertRaises(DatasourceError):
                client.get("/thing/")
        sleep.assert_called_with(2.0)

    def test_html_instead_of_json_is_not_retried(self):
        calls = []

        class Fake:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def read(self):
                return b"<html>gateway timeout</html>"

        def fake_urlopen(request, timeout=None):
            calls.append(1)
            return Fake()

        client = CatchAndStatsClient(base_url="https://example.test/api")
        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            with self.assertRaises(DatasourceError) as caught:
                client.get("/thing/")
        self.assertEqual(len(calls), 1)
        self.assertIn("did not return JSON", str(caught.exception))

    def test_fresh_cache_short_circuits_the_api(self):
        _write_cache(
            f"season-6-v{CACHE_VERSION}.json",
            {"season": {"title": "2026-2027"}, "players": [{"player": "X"}], "fetched_at": "2026-10-18T00:00:00+00:00"},
        )
        client = CatchAndStatsClient(base_url="https://example.test/api", cache_ttl=3600)
        with mock.patch.object(CatchAndStatsClient, "seasons", return_value=[SEASON_ROW]), mock.patch(
            "urllib.request.urlopen", side_effect=AssertionError("the network should not be touched")
        ):
            table = client.season_table("E2026")
        self.assertFalse(table["stale"])
        self.assertEqual(table["players"][0]["player"], "X")

    def test_expired_cache_is_served_when_the_api_is_down(self):
        key = f"season-6-v{CACHE_VERSION}.json"
        _write_cache(
            key,
            {
                "season": {"title": "2026-2027"},
                "players": [{"player": "X"}],
                "teams": [],
                "fetched_at": "2026-10-01T00:00:00+00:00",
            },
        )
        path = cache_dir() / key
        old = time.time() - 7200
        os.utime(path, (old, old))

        client = CatchAndStatsClient(base_url="https://example.test/api", cache_ttl=60)
        with mock.patch.object(CatchAndStatsClient, "seasons", return_value=[SEASON_ROW]), mock.patch(
            "urllib.request.urlopen", side_effect=OSError("network down")
        ), mock.patch("growth.datasource.time.sleep"):
            table = client.season_table("E2026")

        self.assertTrue(table["stale"])
        self.assertIn("not answering", table["warning"])
        self.assertIn("2026-10-01", table["warning"])

    def test_missing_cache_still_raises(self):
        client = CatchAndStatsClient(base_url="https://example.test/api", cache_ttl=60)
        with mock.patch.object(CatchAndStatsClient, "seasons", return_value=[SEASON_ROW]), mock.patch(
            "urllib.request.urlopen", side_effect=OSError("network down")
        ), mock.patch("growth.datasource.time.sleep"):
            with self.assertRaises(DatasourceError):
                client.season_table("E2026")

    def test_empty_season_is_reported_not_returned_empty(self):
        class Fake:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def read(self):
                return json.dumps({"results": [], "next": None}).encode()

        client = CatchAndStatsClient(base_url="https://example.test/api")
        with mock.patch.object(CatchAndStatsClient, "seasons", return_value=[SEASON_ROW]), mock.patch(
            "urllib.request.urlopen", side_effect=lambda *args, **kwargs: Fake()
        ):
            with self.assertRaises(DatasourceError) as caught:
                client.season_table("E2026")
        self.assertIn("no players", str(caught.exception))


class _FakeResponse:
    """Minimal stand-in for a curl_cffi response in client unit tests."""

    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}

    def json(self):
        return self._payload


class _FakeInstagramClient:
    """A stand-in InstagramClient for service tests; records what it was asked for."""

    def __init__(self, comments, reported=None):
        self._comments = list(comments)
        self._reported = reported
        self.calls: list[tuple] = []

    def comments(self, media_pk, amount=None):
        self.calls.append(("comments", media_pk, amount))
        return self._comments[:amount] if amount else list(self._comments)

    def comment_count(self, media_pk):
        self.calls.append(("count", media_pk, None))
        return self._reported


class InstagramClientTests(SimpleTestCase):
    """The client's parsing and loop guards, exercised without touching the network."""

    def _client(self, **kwargs):
        return InstagramClient("sessionid-value-1234567890", **kwargs)

    @mock.patch("growth.instagram.time.sleep")
    def test_comments_paginate_with_min_id_and_dedupe(self, _sleep):
        pages = [
            {
                "comments": [{"pk": "1", "user": {"username": "a"}, "text": "one"}],
                "has_more_comments": True,
                "next_max_id": "CUR1",
            },
            {
                "comments": [
                    {"pk": "1", "user": {"username": "a"}, "text": "one"},
                    {"pk": "2", "user": {"username": "b"}, "text": "two"},
                ],
                "has_more_comments": False,
            },
        ]
        calls: list[dict] = []

        def fake_get(path, params=None):
            calls.append(params or {})
            return _FakeResponse(200, pages[len(calls) - 1])

        with mock.patch.object(InstagramClient, "_get", side_effect=fake_get):
            comments = self._client().comments(123)
        self.assertEqual([comment.pk for comment in comments], ["1", "2"])
        self.assertNotIn("min_id", calls[0])
        self.assertEqual(calls[1]["min_id"], "CUR1")

    @mock.patch("growth.instagram.time.sleep")
    def test_comments_stop_when_a_page_adds_nothing(self, _sleep):
        page = {
            "comments": [{"pk": "1", "user": {"username": "a"}}],
            "has_more_comments": True,
            "next_max_id": "SAME",
        }
        with mock.patch.object(InstagramClient, "_get", return_value=_FakeResponse(200, page)):
            comments = self._client().comments(123)
        self.assertEqual(len(comments), 1)

    def test_comments_cap_at_amount(self):
        page = {
            "comments": [{"pk": str(index), "user": {"username": "a"}} for index in range(5)],
            "has_more_comments": False,
        }
        with mock.patch.object(InstagramClient, "_get", return_value=_FakeResponse(200, page)):
            comments = self._client().comments(123, amount=2)
        self.assertEqual(len(comments), 2)

    def test_validate_falls_back_to_a_profile_read(self):
        def fake_get(path, params=None):
            if "current_user" in path:
                return _FakeResponse(400, {})
            return _FakeResponse(200, {"data": {"user": {"username": "burner"}}})

        with mock.patch.object(InstagramClient, "_get", side_effect=fake_get):
            self.assertEqual(self._client().validate(), "burner")

    def test_validate_uses_current_user_when_available(self):
        with mock.patch.object(
            InstagramClient,
            "_get",
            return_value=_FakeResponse(200, {"user": {"username": "me"}}),
        ):
            self.assertEqual(self._client().validate(), "me")

    def test_missing_sessionid_is_not_configured(self):
        with self.assertRaises(InstagramNotConfigured):
            InstagramClient("")


class InstagramCodecTests(SimpleTestCase):
    """Shortcode ↔ media id is offline maths, so it must be exactly right."""

    def test_known_shortcode_decodes_to_its_media_id(self):
        # Taken from a real post's embed payload.
        self.assertEqual(media_pk_from_shortcode("DWr6G6QkpiS"), 3867440266597275794)

    def test_bad_shortcode_is_rejected(self):
        with self.assertRaises(ValueError):
            media_pk_from_shortcode("has spaces!")

    def test_shortcode_from_url_handles_posts_and_reels(self):
        self.assertEqual(shortcode_from_url("https://www.instagram.com/p/DWr6G6QkpiS/"), "DWr6G6QkpiS")
        self.assertEqual(
            shortcode_from_url("https://www.instagram.com/reel/ABC123_-/?utm_source=ig_web"),
            "ABC123_-",
        )

    def test_non_post_url_is_rejected(self):
        with self.assertRaises(ValueError):
            shortcode_from_url("https://www.instagram.com/nasa/")


class InstagramResearchTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.admin = user_model.objects.create_user(username="ig-admin", password="x", is_staff=True)
        cls.user = user_model.objects.create_user(username="ig-user", password="x")

    def _tracked_post(self, shortcode="DWr6G6QkpiS"):
        return InstagramTrackedPost.objects.create(
            url=f"https://www.instagram.com/p/{shortcode}/",
            shortcode=shortcode,
            media_pk=media_pk_from_shortcode(shortcode),
        )

    def test_sync_post_upserts_comments_and_records_the_reported_total(self):
        post = self._tracked_post()
        comment = FetchedComment(
            pk="c1", author_username="alice", author_full_name="Alice", text="hi", created_at_utc=1700000000
        )
        fake = _FakeInstagramClient([comment], reported=100)

        first = sync_post(post, client=fake)
        self.assertEqual((first.fetched, first.created, first.updated, first.total_seen), (1, 1, 0, 100))

        second = sync_post(post, client=fake)
        self.assertEqual((second.fetched, second.created, second.updated), (1, 0, 1))

        post.refresh_from_db()
        self.assertEqual(post.status, "ok")
        self.assertEqual(post.comment_count, 100)
        self.assertEqual(post.comments.count(), 1)
        stored = post.comments.get()
        self.assertEqual(stored.author_username, "alice")
        self.assertIsNotNone(stored.commented_at)

    def test_sync_post_without_a_reported_total_falls_back_to_fetched(self):
        post = self._tracked_post()
        fake = _FakeInstagramClient([FetchedComment(pk="c1", author_username="bob")])
        sync_post(post, client=fake)
        post.refresh_from_db()
        self.assertEqual(post.comment_count, 1)

    def test_sync_post_honours_the_amount_cap(self):
        post = self._tracked_post()
        many = [FetchedComment(pk=str(index), author_username=f"u{index}") for index in range(5)]
        fake = _FakeInstagramClient(many)
        result = sync_post(post, amount=2, client=fake)
        self.assertEqual(result.fetched, 2)
        self.assertEqual(post.comments.count(), 2)

    def test_adding_a_post_stores_the_media_id_without_network(self):
        self.client.force_authenticate(user=self.user)
        with mock.patch("growth.instagram_service.get_client") as client:
            response = self.client.post(
                "/api/growth/instagram/posts/",
                {"url": "https://www.instagram.com/p/DWr6G6QkpiS/"},
                format="json",
            )
        client.assert_not_called()
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()["comments_stored"], 0)
        post = InstagramTrackedPost.objects.get(shortcode="DWr6G6QkpiS")
        self.assertEqual(post.media_pk, 3867440266597275794)

    def test_adding_the_same_post_twice_is_not_a_duplicate(self):
        self.client.force_authenticate(user=self.user)
        payload = {"url": "https://www.instagram.com/p/DWr6G6QkpiS/"}
        first = self.client.post("/api/growth/instagram/posts/", payload, format="json")
        second = self.client.post("/api/growth/instagram/posts/", payload, format="json")
        self.assertEqual((first.status_code, second.status_code), (201, 200))
        self.assertEqual(InstagramTrackedPost.objects.count(), 1)

    def test_bad_url_is_rejected(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            "/api/growth/instagram/posts/", {"url": "https://example.com/x"}, format="json"
        )
        self.assertEqual(response.status_code, 400)

    @mock.patch("growth.views.sync_post")
    def test_scrape_is_staff_only(self, mock_sync):
        post = self._tracked_post()
        self.client.force_authenticate(user=self.user)
        response = self.client.post(f"/api/growth/instagram/posts/{post.id}/scrape/", {}, format="json")
        self.assertEqual(response.status_code, 403)
        mock_sync.assert_not_called()

    @mock.patch("growth.views.sync_post")
    def test_scrape_reports_counts(self, mock_sync):
        mock_sync.return_value = CommentSyncResult(fetched=5, created=3, updated=2)
        post = self._tracked_post()
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(f"/api/growth/instagram/posts/{post.id}/scrape/", {}, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["created"], 3)
        self.assertEqual(response.json()["post"]["shortcode"], "DWr6G6QkpiS")

    @mock.patch("growth.views.sync_post")
    def test_scrape_maps_a_dead_session_to_400(self, mock_sync):
        mock_sync.side_effect = InstagramSessionInvalid("expired")
        post = self._tracked_post()
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(f"/api/growth/instagram/posts/{post.id}/scrape/", {}, format="json")
        self.assertEqual(response.status_code, 400)
        post.refresh_from_db()
        self.assertEqual(post.status, "error")

    @mock.patch("growth.views.sync_post")
    def test_scrape_maps_rate_limit_to_429(self, mock_sync):
        mock_sync.side_effect = InstagramRateLimited("slow down")
        post = self._tracked_post()
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(f"/api/growth/instagram/posts/{post.id}/scrape/", {}, format="json")
        self.assertEqual(response.status_code, 429)

    @mock.patch("growth.views.sync_post")
    def test_scrape_without_a_session_is_400(self, mock_sync):
        mock_sync.side_effect = InstagramNotConfigured("no sessionid")
        post = self._tracked_post()
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(f"/api/growth/instagram/posts/{post.id}/scrape/", {}, format="json")
        self.assertEqual(response.status_code, 400)

    @override_settings(INSTAGRAM_SCRAPER_ENABLED=False)
    @mock.patch("growth.views.sync_post")
    def test_scrape_is_blocked_when_disabled(self, mock_sync):
        post = self._tracked_post()
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(f"/api/growth/instagram/posts/{post.id}/scrape/", {}, format="json")
        self.assertEqual(response.status_code, 400)
        mock_sync.assert_not_called()

    @mock.patch("growth.views.get_client")
    def test_test_endpoint_reports_the_account(self, mock_get_client):
        mock_get_client.return_value.validate.return_value = "burner_account"
        self.client.force_authenticate(user=self.admin)
        response = self.client.post("/api/growth/instagram/test/", {}, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["username"], "burner_account")

    def test_test_endpoint_is_staff_only(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post("/api/growth/instagram/test/", {}, format="json")
        self.assertEqual(response.status_code, 403)

    def test_analysis_counts_top_and_repeat_commenters(self):
        first = self._tracked_post("DWr6G6QkpiS")
        second = self._tracked_post("DWr6HGjkvoi")
        for index in range(3):
            InstagramComment.objects.create(
                post=first, comment_pk=f"a{index}", author_username="alice", text="hi"
            )
        InstagramComment.objects.create(post=second, comment_pk="a9", author_username="alice", text="again")
        InstagramComment.objects.create(post=first, comment_pk="b1", author_username="bob", text="yo")

        self.client.force_authenticate(user=self.user)
        body = self.client.get("/api/growth/instagram/analysis/").json()
        self.assertEqual(body["totals"]["comments"], 5)
        self.assertEqual(body["totals"]["commenters"], 2)
        self.assertEqual(body["totals"]["repeat_commenters"], 1)
        self.assertEqual(body["top_commenters"][0]["author_username"], "alice")
        self.assertEqual(body["top_commenters"][0]["posts"], 2)

    def test_comments_endpoint_filters_by_post(self):
        first = self._tracked_post("DWr6G6QkpiS")
        second = self._tracked_post("DWr6HGjkvoi")
        InstagramComment.objects.create(post=first, comment_pk="1", author_username="alice", text="a")
        InstagramComment.objects.create(post=second, comment_pk="2", author_username="bob", text="b")

        self.client.force_authenticate(user=self.user)
        body = self.client.get(f"/api/growth/instagram/comments/?post={first.id}").json()
        self.assertEqual(body["count"], 1)
        self.assertEqual(body["results"][0]["author_username"], "alice")

    def test_export_returns_csv(self):
        post = self._tracked_post()
        InstagramComment.objects.create(
            post=post, comment_pk="1", author_username="alice", text="nice, \"quoted\""
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/growth/instagram/export/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
        self.assertIn("alice", response.content.decode())
        self.assertIn("author_username", response.content.decode())

    def test_meta_reports_instagram_configuration(self):
        self.client.force_authenticate(user=self.user)
        # Avoid the real season fetch; the meta view tolerates a datasource error.
        with mock.patch("growth.views._seasons", return_value=([], "")):
            body = self.client.get("/api/growth/meta/").json()
        self.assertIn("instagram_configured", body)

class PlaybookRunTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="playbook-user", password="pw")
        self.client.force_authenticate(self.user)
        Channel.objects.create(name="Instagram", channel_type="instagram")
        Channel.objects.create(name="X", channel_type="x")
        self.playbook = Playbook.objects.create(
            name="Test series",
            description="A series",
            default_locales=["el", "en"],
            default_platforms=["instagram", "x"],
        )
        PlaybookSlot.objects.create(
            playbook=self.playbook,
            order=0,
            day_offset=0,
            time="20:00",
            platform="instagram",
            format="carousel",
            content_kind="top8",
            locales=["el"],
            title_template="Hero carousel — {round}",
            brief="Cover, eight teams, CTA.",
            utm_content_template="carousel_el",
        )
        PlaybookSlot.objects.create(
            playbook=self.playbook,
            order=1,
            day_offset=2,
            time="21:00",
            platform="x",
            format="thread",
            content_kind="top8",
            locales=[],
            title_template="Thread — {round}",
            brief="Eight tweets.",
            utm_content_template="thread_{locale}",
        )

    def test_preview_uses_start_date_and_utm_content(self):
        response = self.client.post(
            f"/api/playbooks/{self.playbook.id}/preview/",
            {
                "start_date": "2026-11-04",
                "round_label": "Round 8",
                "locales": ["el", "en"],
                "platforms": ["instagram", "x"],
                "utm_campaign": "top8_r8",
                "landing_path": "top8",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertEqual(body["count"], 3)  # IG is Greek only; X has two locales.
        self.assertEqual(body["start_date"], "2026-11-04")
        self.assertEqual(body["end_date"], "2026-11-06")
        self.assertEqual(body["landing_path"], "/top8")
        instagram = next(item for item in body["items"] if item["platform"] == "instagram")
        self.assertIn("Round 8", instagram["title"])
        self.assertEqual(instagram["utm_content"], "carousel_el")
        self.assertIn("utm_content=carousel_el", instagram["link"])
        self.assertTrue(instagram["link"].startswith("https://catchandstats.com/top8?"))
        x_titles = [item["title"] for item in body["items"] if item["platform"] == "x"]
        self.assertEqual(len(x_titles), 2)
        self.assertTrue(any("[EN]" in title for title in x_titles))

    def test_run_creates_new_campaign_each_time(self):
        first = self.client.post(
            f"/api/playbooks/{self.playbook.id}/run/",
            {"start_date": "2026-11-04", "round_label": "Round 8"},
            format="json",
        )
        second = self.client.post(
            f"/api/playbooks/{self.playbook.id}/run/",
            {"start_date": "2026-11-18", "round_label": "Round 10"},
            format="json",
        )
        self.assertEqual(first.status_code, 201, first.content)
        self.assertEqual(second.status_code, 201, second.content)
        self.assertNotEqual(first.json()["campaign"]["id"], second.json()["campaign"]["id"])
        self.assertEqual(ContentItem.objects.count(), 6)
        self.assertEqual(Campaign.objects.count(), 2)
        self.assertEqual(Task.objects.count(), 6)
        self.assertEqual(KpiTarget.objects.count(), 20)

    def test_paid_slot_creates_a_planned_boost(self):
        slot = self.playbook.slots.first()
        slot.paid_budget = "150.00"
        slot.save(update_fields=["paid_budget"])
        response = self.client.post(
            f"/api/playbooks/{self.playbook.id}/run/",
            {"start_date": "2026-11-04", "round_label": "Round 8"},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()["boosts_created"], 1)
        self.assertEqual(Boost.objects.count(), 1)
        boost = Boost.objects.get()
        self.assertEqual(float(boost.total_budget), 150.0)
        self.assertEqual(boost.status, "planned")

    def test_duplicate_copies_slots_without_touching_source(self):
        response = self.client.post(
            f"/api/playbooks/{self.playbook.id}/duplicate/",
            {"name": "Copy"},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        clone = Playbook.objects.get(name="Copy")
        self.assertEqual(clone.slots.count(), self.playbook.slots.count())
        self.assertFalse(clone.is_seeded)
        self.assertEqual(self.playbook.slots.count(), 2)


class TeamBuilderTests(SimpleTestCase):
    def test_top8_sorts_by_record_then_net_rating(self):
        teams = [
            {"team_title": "Alpha", "team_id": 1, "wins": 5, "losses": 2, "net_rating": 9.0, "games": 7, "season_title": "2026-2027"},
            {"team_title": "Beta", "team_id": 2, "wins": 6, "losses": 1, "net_rating": 2.0, "games": 7, "season_title": "2026-2027"},
            {"team_title": "Gamma", "team_id": 3, "wins": 5, "losses": 2, "net_rating": 14.0, "games": 7, "season_title": "2026-2027"},
        ]
        table = build_top8_table(teams, top_n=3)
        self.assertEqual([row["team"] for row in table["rows"]], ["Beta", "Gamma", "Alpha"])
        self.assertEqual(table["rows"][1]["record"], "5-2")

    def test_team_card_includes_previous_season_note(self):
        team = {
            "team_title": "Panathinaikos AKTOR Athens",
            "team_id": 6,
            "wins": 6,
            "losses": 1,
            "record": "6-1",
            "net_rating": 18.4,
            "offensive_rating": 117.33,
            "defensive_rating": 98.93,
            "ts_pct": 0.603,
            "efg_pct": 0.571,
            "tov_pct": 0.139,
            "season_title": "2026-2027",
        }
        previous = {"team_title": "Panathinaikos AKTOR Athens", "offensive_rating": 115.0}
        card = build_team_card(team, previous=previous, rank=1, total=8)
        self.assertEqual(card["title"], "Panathinaikos")
        self.assertEqual(card["headline"], "18.40")
        self.assertIn("#1 of 8", card["headline_note"])
        self.assertTrue(any("last season" in row["note"] for row in card["rows"]))


class CaptionPlatformTests(SimpleTestCase):
    def test_new_platforms_and_x_thread(self):
        spec = {
            "kind": "top8",
            "title": "Top 8 after 7 rounds",
            "rows": [
                {"team": f"Team {index}", "record": "6-1", "net": f"{10 - index}.00"}
                for index in range(1, 9)
            ],
        }
        drafts = build_captions(spec, link="https://example.com/?utm_campaign=x", platforms=("x", "facebook", "youtube"), locales=("en",))
        self.assertEqual({draft["platform"] for draft in drafts}, {"x", "facebook", "youtube"})
        x = next(draft for draft in drafts if draft["platform"] == "x")
        self.assertGreater(len(x["thread"]), 8)
        self.assertTrue(all(len(tweet) <= 280 for tweet in x["thread"]))
        facebook = next(draft for draft in drafts if draft["platform"] == "facebook")
        self.assertIn("Top 8", facebook["text"])
        youtube = next(draft for draft in drafts if draft["platform"] == "youtube")
        self.assertTrue(youtube["title"])


class CardSetApiTests(APITestCase):
    def setUp(self):
        self.media = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.media)
        self.override.enable()
        self.user = get_user_model().objects.create_user(username="set-user", password="pw")
        self.client.force_authenticate(self.user)

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.media, ignore_errors=True)

    def test_create_and_download_zip(self):
        specs = [
            {"kind": "top8", "title": "Cover", "subtitle": "2026-2027", "rows": []},
            {
                "kind": "top8",
                "layout": "table",
                "title": "Table",
                "subtitle": "Net rating",
                "columns": ["#", "Team", "Rec", "Net"],
                "rows": [
                    {"rank": 1, "team": "Alpha", "record": "6-1", "net": "18.40", "value": "18.40"},
                    {"rank": 2, "team": "Beta", "record": "5-2", "net": "9.20", "value": "9.20"},
                ],
            },
        ]
        response = self.client.post(
            "/api/card-sets/",
            {"format": "instagram", "title": "Test set", "specs": specs},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        self.assertEqual(len(body["slides"]), 2)
        self.assertTrue(all(slide["image_url"] for slide in body["slides"]))
        self.assertEqual(CardSet.objects.count(), 1)
        self.assertEqual(StatCard.objects.count(), 2)

        download = self.client.get(f"/api/card-sets/{body['id']}/download/")
        self.assertEqual(download.status_code, 200)
        self.assertEqual(download["Content-Type"], "application/zip")
        self.assertTrue(download.content.startswith(b"PK"))
