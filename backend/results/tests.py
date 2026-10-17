from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APITestCase

from campaigns.models import Campaign

from .models import DailyMetric


class MetricImportCsvTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="importer", password="pw123456")
        self.client.force_authenticate(self.user)
        self.campaign = Campaign.objects.create(name="Fall Baskets", budget="500.00")

    def upload(self, body: str):
        f = SimpleUploadedFile("metrics.csv", body.encode("utf-8"), content_type="text/csv")
        return self.client.post("/api/metrics/import-csv/", {"file": f}, format="multipart")

    def test_import_reports_bad_rows_and_keeps_going(self):
        body = (
            "campaign,date,revenue,orders,spend,ctr,roas\n"
            f"{self.campaign.id},2026-10-01,120.00,4,40.00,0.4,3.0\n"
            "999,2026-10-01,10,1,5,0.1,2\n"
            f"{self.campaign.id},not-a-date,10,1,5,0.1,2\n"
        )
        r = self.upload(body)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data["created"], 1)
        self.assertEqual(r.data["updated"], 0)
        self.assertEqual(r.data["error_count"], 2)
        self.assertEqual([e["row"] for e in r.data["errors"]], [3, 4])
        self.assertEqual(DailyMetric.objects.count(), 1)

    def test_import_derives_roas_when_missing(self):
        body = "campaign,date,revenue,orders,spend\n" f"{self.campaign.id},2026-10-02,200.00,5,50.00\n"
        r = self.upload(body)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data["created"], 1)
        metric = DailyMetric.objects.get(campaign=self.campaign, date="2026-10-02")
        self.assertAlmostEqual(metric.roas, 4.0)

    def test_import_updates_existing_row(self):
        body = "campaign,date,revenue,orders,spend,roas\n" f"{self.campaign.id},2026-10-03,10.00,1,5.00,2.0\n"
        first = self.upload(body)
        self.assertEqual(first.data["created"], 1)
        second = self.upload(body.replace("10.00", "20.00"))
        self.assertEqual(second.data["created"], 0)
        self.assertEqual(second.data["updated"], 1)
        metric = DailyMetric.objects.get(campaign=self.campaign, date="2026-10-03")
        self.assertEqual(str(metric.revenue), "20.00")

    def test_import_accepts_campaign_id_alias_and_blank_lines(self):
        body = (
            "campaign_id,date,spend\n"
            "\n"
            f"{self.campaign.id},2026-10-04,7.50\n"
        )
        r = self.upload(body)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data["created"], 1)
        self.assertEqual(r.data["error_count"], 0)

    def test_import_marks_rows_manual_and_overwrites_synced_rows(self):
        DailyMetric.objects.create(
            campaign=self.campaign, date="2026-10-05", revenue="10.00", spend="1.00",
            source=DailyMetric.SOURCE_GA4,
        )
        body = "campaign,date,revenue,orders,spend\n" f"{self.campaign.id},2026-10-05,20.00,2,5.00\n"
        r = self.upload(body)
        self.assertEqual(r.data["updated"], 1)
        metric = DailyMetric.objects.get(campaign=self.campaign, date="2026-10-05")
        self.assertEqual(metric.source, DailyMetric.SOURCE_MANUAL)
        self.assertEqual(str(metric.revenue), "20.00")


class MetricSourceTests(APITestCase):
    """`source` is reporting metadata — clients cannot set it."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(username="importer", password="pw123456")
        self.client.force_authenticate(self.user)
        self.campaign = Campaign.objects.create(name="Fall Baskets", budget="500.00")

    def test_source_is_exposed_on_read(self):
        DailyMetric.objects.create(
            campaign=self.campaign, date="2026-10-01", revenue="5.00", source=DailyMetric.SOURCE_GA4
        )
        r = self.client.get("/api/metrics/", {"campaign": self.campaign.id})
        self.assertEqual(r.data["results"][0]["source"], "ga4")

    def test_source_sent_by_a_client_is_ignored(self):
        r = self.client.post(
            "/api/metrics/",
            {"campaign": self.campaign.id, "date": "2026-10-02", "source": "ga4"},
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.data["source"], DailyMetric.SOURCE_MANUAL)
        self.assertEqual(DailyMetric.objects.get().source, DailyMetric.SOURCE_MANUAL)


class MetricFilterExportTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="exporter", password="pw123456")
        self.client.force_authenticate(self.user)
        self.campaign = Campaign.objects.create(name="Fall Baskets", budget="500.00")
        self.other = Campaign.objects.create(name="Winter", budget="200.00")
        DailyMetric.objects.create(
            campaign=self.campaign, date="2026-10-01", revenue="10.00", orders=1, spend="5.00", ctr=0.5, roas=2.0
        )
        DailyMetric.objects.create(
            campaign=self.campaign, date="2026-09-01", revenue="20.00", orders=2, spend="10.00", ctr=0.4, roas=2.0
        )
        DailyMetric.objects.create(
            campaign=self.other, date="2026-10-02", revenue="30.00", orders=3, spend="15.00", ctr=0.3, roas=2.0
        )

    def test_filter_by_date_range(self):
        r = self.client.get("/api/metrics/", {"date__gte": "2026-10-01", "date__lte": "2026-10-31"})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data["count"], 2)

    def test_export_respects_filters(self):
        r = self.client.get(
            "/api/metrics/export-csv/",
            {"campaign": self.campaign.id, "date__gte": "2026-10-01"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/csv", r["Content-Type"])
        lines = r.content.decode().strip().splitlines()
        self.assertEqual(lines[0], "campaign,date,revenue,orders,spend,ctr,roas")
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[1].startswith(f"{self.campaign.id},2026-10-01"))

    def test_export_round_trips_through_import(self):
        exported = self.client.get("/api/metrics/export-csv/")
        body = exported.content.decode()
        f = SimpleUploadedFile("roundtrip.csv", body.encode("utf-8"), content_type="text/csv")
        r = self.client.post("/api/metrics/import-csv/", {"file": f}, format="multipart")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data["created"], 0)
        self.assertEqual(r.data["updated"], 3)
        self.assertEqual(r.data["error_count"], 0)
