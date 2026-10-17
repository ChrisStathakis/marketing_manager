from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APITestCase

from campaigns.models import Campaign
from channels.models import Channel

from .models import AdSpend


class AdSpendApiTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="spender", password="pw123456")
        self.client.force_authenticate(self.user)
        self.campaign = Campaign.objects.create(name="Fall Baskets", budget="500.00")

    def test_duplicate_null_channel_row_rejected(self):
        payload = {"campaign": self.campaign.id, "date": "2026-10-01", "spend": "10.00"}
        first = self.client.post("/api/spend/", payload, format="json")
        self.assertEqual(first.status_code, 201, first.content)
        second = self.client.post("/api/spend/", payload, format="json")
        self.assertEqual(second.status_code, 400, second.content)
        self.assertEqual(AdSpend.objects.count(), 1)

    def test_distinct_channel_row_allowed(self):
        channel = Channel.objects.create(name="Main IG", channel_type="instagram")
        self.client.post("/api/spend/", {"campaign": self.campaign.id, "date": "2026-10-01"}, format="json")
        r = self.client.post(
            "/api/spend/",
            {"campaign": self.campaign.id, "channel": channel.id, "date": "2026-10-01"},
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.content)


class AdSpendImportCsvTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="importer", password="pw123456")
        self.client.force_authenticate(self.user)
        self.campaign = Campaign.objects.create(name="Fall Baskets", budget="500.00")
        self.channel = Channel.objects.create(name="Main IG", channel_type="instagram")

    def upload(self, body: str):
        f = SimpleUploadedFile("spend.csv", body.encode("utf-8"), content_type="text/csv")
        return self.client.post("/api/spend/import-csv/", {"file": f}, format="multipart")

    def test_import_with_channel_and_row_errors(self):
        body = (
            "campaign,channel,date,spend,impressions,clicks,conversions\n"
            f"{self.campaign.id},{self.channel.id},2026-10-01,30.00,1000,50,5\n"
            f"{self.campaign.id},424242,2026-10-01,10.00,100,1,0\n"
            f"{self.campaign.id},{self.channel.id},2026-10-02,-5,100,1,0\n"
        )
        r = self.upload(body)
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data["created"], 1)
        self.assertEqual(r.data["error_count"], 2)
        self.assertEqual([e["row"] for e in r.data["errors"]], [3, 4])

    def test_import_marks_rows_manual(self):
        AdSpend.objects.create(
            campaign=self.campaign, date="2026-10-03", spend="1.00", source=AdSpend.SOURCE_GOOGLE_ADS
        )
        body = "campaign,date,spend\n" f"{self.campaign.id},2026-10-03,9.00\n"
        r = self.upload(body)
        self.assertEqual(r.data["updated"], 1)
        row = AdSpend.objects.get(campaign=self.campaign, date="2026-10-03")
        self.assertEqual(row.source, AdSpend.SOURCE_MANUAL)
        self.assertEqual(str(row.spend), "9.00")


class AdSpendExportTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="exporter", password="pw123456")
        self.client.force_authenticate(self.user)
        self.campaign = Campaign.objects.create(name="Fall Baskets", budget="500.00")
        self.channel = Channel.objects.create(name="Main IG", channel_type="instagram")
        AdSpend.objects.create(campaign=self.campaign, channel=self.channel, date="2026-10-01", spend="30.00")
        AdSpend.objects.create(campaign=self.campaign, date="2026-10-02", spend="12.00")

    def test_export_includes_null_channel_as_empty(self):
        r = self.client.get("/api/spend/export-csv/")
        self.assertEqual(r.status_code, 200)
        lines = r.content.decode().strip().splitlines()
        self.assertEqual(lines[0], "campaign,channel,date,spend,impressions,clicks,conversions")
        self.assertEqual(len(lines), 3)
        self.assertIn(f"{self.campaign.id},,2026-10-02", lines[2])

    def test_filter_by_channel(self):
        r = self.client.get("/api/spend/", {"channel": self.channel.id})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data["count"], 1)
