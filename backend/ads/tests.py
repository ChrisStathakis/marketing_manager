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
