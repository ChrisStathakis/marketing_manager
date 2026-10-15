from datetime import timedelta

from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.utils import timezone

from campaigns.models import Campaign
from results.models import DailyMetric


class RegisterTests(APITestCase):
    def test_register_disabled_by_default(self):
        with override_settings(ALLOW_REGISTRATION=False):
            r = self.client.post("/api/register/", {"username": "nope", "password": "1234"}, format="json")
        self.assertEqual(r.status_code, 403, r.content)

    @override_settings(ALLOW_REGISTRATION=True)
    def test_register_with_short_password_and_login(self):
        r = self.client.post("/api/register/", {"username": "newbie", "password": "1234"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertIn("access", r.data)
        t = self.client.post("/api/token/", {"username": "newbie", "password": "1234"}, format="json")
        self.assertEqual(t.status_code, 200, t.content)

    @override_settings(ALLOW_REGISTRATION=True)
    def test_register_duplicate_username_rejected(self):
        self.client.post("/api/register/", {"username": "dupe", "password": "1234"}, format="json")
        r = self.client.post("/api/register/", {"username": "dupe", "password": "1234"}, format="json")
        self.assertEqual(r.status_code, 400)


class CampaignFlowTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="u1", password="pw123456")
        self.client.force_authenticate(self.user)

    def test_create_campaign_and_metric_and_rule_suggestion(self):
        r = self.client.post("/api/campaigns/", {"name": "Fall Baskets", "budget": "500.00"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        cid = r.data["id"]
        m = self.client.post("/api/metrics/", {
            "campaign": cid, "date": "2026-10-01", "revenue": "120.00",
            "orders": 4, "spend": "40.00", "ctr": 0.4, "roas": 3.0,
        }, format="json")
        self.assertEqual(m.status_code, 201, m.content)
        g = self.client.post("/api/suggestions/generate/", {"campaign": cid}, format="json")
        self.assertEqual(g.status_code, 201, g.content)
        self.assertTrue(len(g.data) >= 1)
        d = self.client.get("/api/dashboard/summary/")
        self.assertEqual(d.status_code, 200)
        self.assertEqual(d.data["revenue"], 120.0)


class HealthConfigTests(APITestCase):
    def test_health_reports_database(self):
        r = self.client.get("/api/health/")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["ok"])
        self.assertTrue(r.data["database"])

    def test_config_is_public(self):
        r = self.client.get("/api/config/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("registration_enabled", r.data)


class DashboardRangeTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="analyst", password="pw123456")
        self.client.force_authenticate(self.user)
        self.campaign = Campaign.objects.create(name="Fall Baskets", budget="500.00")
        # Current window: Oct 10-12. Previous window: Oct 7-9.
        DailyMetric.objects.create(
            campaign=self.campaign, date="2026-10-10", revenue="100.00", orders=2, spend="50.00", ctr=0.5, roas=2.0
        )
        DailyMetric.objects.create(
            campaign=self.campaign, date="2026-10-11", revenue="60.00", orders=1, spend="10.00", ctr=0.4, roas=6.0
        )
        DailyMetric.objects.create(
            campaign=self.campaign, date="2026-10-08", revenue="80.00", orders=4, spend="40.00", ctr=0.3, roas=2.0
        )

    def summary(self, **params):
        r = self.client.get("/api/dashboard/summary/", params)
        self.assertEqual(r.status_code, 200, r.content)
        return r.data

    def test_range_filters_totals_series_and_campaigns(self):
        data = self.summary(date__gte="2026-10-10", date__lte="2026-10-12")
        self.assertEqual(data["revenue"], 160.0)
        self.assertEqual(data["orders"], 3)
        self.assertEqual([p["date"] for p in data["series"]], ["2026-10-10", "2026-10-11"])
        self.assertEqual(data["campaigns"][0]["revenue"], 160.0)
        self.assertEqual(data["range"], {"start": "2026-10-10", "end": "2026-10-12"})

    def test_deltas_compare_previous_same_length_window(self):
        data = self.summary(date__gte="2026-10-10", date__lte="2026-10-12")
        # Previous window Oct 7-9: revenue 80, spend 40, orders 4, roas 2.0.
        # Current window: revenue 160, spend 60, orders 3, roas 2.67.
        self.assertEqual(data["deltas"]["revenue"], 100.0)
        self.assertEqual(data["deltas"]["spend"], 50.0)
        self.assertEqual(data["deltas"]["orders"], -25.0)
        self.assertEqual(data["deltas"]["roas"], 33.5)

    def test_no_range_returns_all_time_and_null_deltas(self):
        data = self.summary()
        self.assertEqual(data["revenue"], 240.0)
        self.assertEqual(len(data["series"]), 3)
        self.assertIsNone(data["deltas"]["revenue"])
        self.assertEqual(data["range"], {"start": None, "end": None})

    def test_days_param_uses_local_today(self):
        data = self.summary(days="3")
        end = timezone.localdate()
        self.assertEqual(data["range"]["end"], end.isoformat())
        self.assertEqual(data["range"]["start"], (end - timedelta(days=2)).isoformat())
