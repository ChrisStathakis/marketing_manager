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
