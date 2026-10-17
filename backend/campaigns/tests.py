from datetime import timedelta
from io import StringIO
import json

from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.models import Sum
from django.test import override_settings
from django.utils import timezone

from ads.models import AdSpend
from campaigns.models import Campaign
from channels.models import Channel
from content.models import ContentItem
from integrations.models import IntegrationCredential
from plans.models import Task
from results.models import DailyMetric
from shop.models import OrderRef, Product
from suggestions.models import Suggestion


class RegisterTests(APITestCase):
    def test_register_open_until_first_user_then_admin(self):
        # No accounts yet: registration is open and the first user is the admin.
        self.assertFalse(get_user_model().objects.exists())
        r = self.client.post("/api/register/", {"username": "owner", "password": "1"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertTrue(r.data["is_admin"])
        owner = get_user_model().objects.get(username="owner")
        self.assertTrue(owner.is_staff and owner.is_superuser)

    def test_register_closed_once_a_user_exists(self):
        get_user_model().objects.create_user(username="admin", password="pw123456")
        with override_settings(ALLOW_REGISTRATION=False):
            r = self.client.post("/api/register/", {"username": "nope", "password": "1"}, format="json")
        self.assertEqual(r.status_code, 403, r.content)

    @override_settings(ALLOW_REGISTRATION=True)
    def test_register_with_short_password_and_login(self):
        get_user_model().objects.create_user(username="admin", password="pw123456")
        r = self.client.post("/api/register/", {"username": "newbie", "password": "1234"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertIn("access", r.data)
        self.assertFalse(r.data["is_admin"])
        t = self.client.post("/api/token/", {"username": "newbie", "password": "1234"}, format="json")
        self.assertEqual(t.status_code, 200, t.content)

    @override_settings(ALLOW_REGISTRATION=True)
    def test_register_duplicate_username_rejected(self):
        get_user_model().objects.create_user(username="admin", password="pw123456")
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


class SeedDemoCommandTests(APITestCase):
    def test_seed_demo_populates_and_guards_against_rerun(self):
        get_user_model().objects.create_user(username="seedowner", password="pw123456")
        call_command("seed_demo", stdout=StringIO())
        self.assertGreater(Campaign.objects.count(), 0)
        self.assertGreater(DailyMetric.objects.count(), 0)
        self.assertGreater(AdSpend.objects.count(), 0)
        self.assertGreater(ContentItem.objects.count(), 0)
        self.assertGreater(Product.objects.count(), 0)
        self.assertGreater(OrderRef.objects.count(), 0)
        self.assertGreater(Task.objects.count(), 0)
        self.assertGreater(Suggestion.objects.count(), 0)
        self.assertTrue(Campaign.objects.filter(owner__username="seedowner").exists())

        # Metrics and ad spend stay consistent for the same campaign/day.
        metric = DailyMetric.objects.filter(campaign__utm_campaign="spring-retargeting").order_by("-date").first()
        spend_sum = metric.campaign.ad_spends.filter(date=metric.date).aggregate(total=Sum("spend"))["total"]
        self.assertEqual(metric.spend, spend_sum)

        # Second run without --reset is guarded.
        with self.assertRaises(CommandError):
            call_command("seed_demo", stdout=StringIO())

    def test_seed_demo_reset_keeps_users_and_saved_api_keys(self):
        user = get_user_model().objects.create_user(username="seedowner", password="pw123456")
        IntegrationCredential.objects.create(provider="openai", key_encrypted="token", key_hint="0000")
        call_command("seed_demo", stdout=StringIO())
        call_command("seed_demo", "--reset", stdout=StringIO())
        self.assertTrue(get_user_model().objects.filter(pk=user.pk).exists())
        self.assertTrue(IntegrationCredential.objects.filter(provider="openai").exists())
        self.assertGreater(Campaign.objects.count(), 0)

    def test_seed_demo_owner_option_selects_user(self):
        get_user_model().objects.create_user(username="first", password="pw123456")
        target = get_user_model().objects.create_user(username="second", password="pw123456")
        call_command("seed_demo", "--owner", "second", stdout=StringIO())
        self.assertTrue(Campaign.objects.filter(owner=target).exists())
        self.assertFalse(Campaign.objects.filter(owner__username="first").exists())

    def test_seed_demo_unknown_owner_fails_before_writing(self):
        get_user_model().objects.create_user(username="someone", password="pw123456")
        with self.assertRaises(CommandError):
            call_command("seed_demo", "--owner", "ghost", stdout=StringIO())
        self.assertEqual(Campaign.objects.count(), 0)


class BackupTests(APITestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser("admin", "admin@example.com", "pw123456")
        self.client.force_authenticate(self.admin)

    def _seed(self):
        channel = Channel.objects.create(name="Instagram", channel_type="instagram", handle="@shop")
        campaign = Campaign.objects.create(name="Fall", budget="100.00", utm_campaign="fall", owner=self.admin)
        ContentItem.objects.create(campaign=campaign, channel=channel, title="Post")
        DailyMetric.objects.create(
            campaign=campaign, date="2026-10-01", revenue="10.00", orders=1, spend="5.00", ctr=0.1, roas=2.0
        )
        AdSpend.objects.create(campaign=campaign, channel=channel, date="2026-10-01", spend="5.00")
        Product.objects.create(external_id="p1", name="Basket", price="10.00")
        OrderRef.objects.create(external_id="o1", campaign=campaign, total="10.00")
        suggestion = Suggestion.objects.create(campaign=campaign, title="Try reels")
        Task.objects.create(campaign=campaign, title="Do it", suggestion=suggestion)

    def test_export_then_restore_round_trip(self):
        self._seed()
        export = self.client.get("/api/backup/export/")
        self.assertEqual(export.status_code, 200, export.content)
        payload = json.loads(export.content)
        self.assertEqual(payload["format"], "marketing-manager-backup")
        self.assertEqual(payload["counts"]["campaigns.Campaign"], 1)
        # Owner is exported by username so it survives a restore into a new DB.
        self.assertEqual(payload["data"]["campaigns.Campaign"][0]["owner"], "admin")
        self.assertNotIn("auth.User", payload["data"])

        Campaign.objects.all().delete()
        self.assertEqual(Campaign.objects.count(), 0)
        self.assertEqual(ContentItem.objects.count(), 0)

        upload = SimpleUploadedFile("backup.json", json.dumps(payload).encode())
        r = self.client.post("/api/backup/restore/", {"file": upload, "confirm": "replace"}, format="multipart")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data["kind"], "json")
        self.assertEqual(Campaign.objects.count(), 1)
        self.assertEqual(Campaign.objects.get().owner, self.admin)
        self.assertEqual(ContentItem.objects.count(), 1)
        self.assertEqual(DailyMetric.objects.count(), 1)
        self.assertEqual(Task.objects.count(), 1)
        # auto_now/auto_now_add timestamps survive the restore.
        self.assertEqual(Campaign.objects.get().created_at.date(), timezone.localdate())

    def test_restore_maps_unknown_owner_to_none(self):
        self._seed()
        payload = json.loads(self.client.get("/api/backup/export/").content)
        payload["data"]["campaigns.Campaign"][0]["owner"] = "ghost"
        upload = SimpleUploadedFile("backup.json", json.dumps(payload).encode())
        r = self.client.post("/api/backup/restore/", {"file": upload, "confirm": "replace"}, format="multipart")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIsNone(Campaign.objects.get().owner)

    def test_restore_requires_confirm(self):
        self._seed()
        export = json.loads(self.client.get("/api/backup/export/").content)
        upload = SimpleUploadedFile("backup.json", json.dumps(export).encode())
        r = self.client.post("/api/backup/restore/", {"file": upload}, format="multipart")
        self.assertEqual(r.status_code, 400, r.content)

    def test_restore_requires_staff(self):
        self._seed()
        export = json.loads(self.client.get("/api/backup/export/").content)
        plain = get_user_model().objects.create_user("plain", password="pw123456")
        self.client.force_authenticate(plain)
        upload = SimpleUploadedFile("backup.json", json.dumps(export).encode())
        r = self.client.post("/api/backup/restore/", {"file": upload, "confirm": "replace"}, format="multipart")
        self.assertEqual(r.status_code, 403, r.content)
        self.assertEqual(Campaign.objects.count(), 1)

    def test_restore_rejects_unknown_file(self):
        upload = SimpleUploadedFile("notes.txt", b"definitely not a backup")
        r = self.client.post("/api/backup/restore/", {"file": upload, "confirm": "replace"}, format="multipart")
        self.assertEqual(r.status_code, 400, r.content)

    def test_database_download_streams_sqlite(self):
        r = self.client.get("/api/backup/database/")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(bytes(r.content).startswith(b"SQLite format 3\x00"))
