from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from campaigns.models import Campaign
from channels.models import Channel

from .models import ContentItem


class ContentItemTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="planner", password="pw123456")
        self.client.force_authenticate(self.user)
        self.campaign = Campaign.objects.create(name="Fall Baskets", budget="500.00")
        self.channel = Channel.objects.create(name="Main IG", channel_type="instagram")
        self.in_month = ContentItem.objects.create(
            campaign=self.campaign,
            channel=self.channel,
            title="Promo post",
            status="scheduled",
            publish_at="2026-10-10T09:00:00Z",
        )
        self.out_of_month = ContentItem.objects.create(
            campaign=self.campaign,
            title="Later post",
            status="draft",
            publish_at="2026-11-15T09:00:00Z",
        )

    def test_filter_by_publish_at_range(self):
        r = self.client.get(
            "/api/content/",
            {"publish_at__gte": "2026-10-01T00:00:00Z", "publish_at__lte": "2026-10-31T23:59:59Z"},
        )
        self.assertEqual(r.status_code, 200, r.content)
        ids = [row["id"] for row in r.data["results"]]
        self.assertEqual(ids, [self.in_month.id])

    def test_filter_by_status_and_campaign(self):
        r = self.client.get("/api/content/", {"status": "draft", "campaign": self.campaign.id})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data["count"], 1)
        self.assertEqual(r.data["results"][0]["id"], self.out_of_month.id)

    def test_create_content_item(self):
        r = self.client.post(
            "/api/content/",
            {
                "campaign": self.campaign.id,
                "channel": self.channel.id,
                "title": "New reel",
                "status": "draft",
                "link": "https://shop.example.com/basket",
                "utm_source": "instagram",
                "utm_medium": "social",
                "utm_campaign": "fall-baskets",
            },
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.content)
