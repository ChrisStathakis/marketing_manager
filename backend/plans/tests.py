from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from campaigns.models import Campaign

from .models import Task


class TaskCalendarTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="planner", password="pw123456")
        self.client.force_authenticate(self.user)
        self.campaign = Campaign.objects.create(name="Fall Baskets", budget="500.00")
        Task.objects.create(campaign=self.campaign, title="Brief videos", due_date="2026-10-05")
        Task.objects.create(campaign=self.campaign, title="Next month", due_date="2026-11-02")
        Task.objects.create(campaign=self.campaign, title="No date")

    def test_filter_by_due_date_range(self):
        r = self.client.get("/api/tasks/", {"due_date__gte": "2026-10-01", "due_date__lte": "2026-10-31"})
        self.assertEqual(r.status_code, 200, r.content)
        titles = [row["title"] for row in r.data["results"]]
        self.assertEqual(titles, ["Brief videos"])

    def test_filter_by_done(self):
        r = self.client.get("/api/tasks/", {"done": "false"})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data["count"], 3)
