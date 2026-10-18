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
from growth.builders import build_spec, team_short
from growth.cards import SIZES, render_card
from growth.captions import build_captions
from growth.datasource import CACHE_VERSION, CatchAndStatsClient, DatasourceError, cache_dir, priority_country, _write_cache
from growth.insights import build_insights
from growth.metrics import format_metric
from growth.models import GrowthExperiment, PostPerformance, StatCard, TrafficSnapshot
from growth.planning import site_link
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

    def test_site_link_keeps_utm_parameters(self):
        link = site_link("https://catchandstats.com", "reddit", "euroleague-organic")
        self.assertEqual(
            link,
            "https://catchandstats.com/?utm_source=reddit&utm_medium=social&utm_campaign=euroleague-organic",
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
            ["date", "sessionSource", "sessionMedium"],
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
