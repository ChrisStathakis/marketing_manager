from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from campaigns.models import Campaign
from results.models import DailyMetric


class RegisterTests(APITestCase):
    def test_register_with_short_password_and_login(self):
        r = self.client.post("/api/register/", {"username": "newbie", "password": "1234"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertIn("access", r.data)
        t = self.client.post("/api/token/", {"username": "newbie", "password": "1234"}, format="json")
        self.assertEqual(t.status_code, 200, t.content)

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
