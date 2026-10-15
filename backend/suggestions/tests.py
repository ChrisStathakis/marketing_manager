from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from campaigns.models import Campaign
from plans.models import Task
from results.models import DailyMetric

from .models import Suggestion


class SuggestionWorkflowTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="coach", password="pw123456")
        self.client.force_authenticate(self.user)
        self.campaign = Campaign.objects.create(name="Fall Baskets", budget="500.00")
        # Low CTR + no upcoming content -> generates rule suggestions.
        DailyMetric.objects.create(
            campaign=self.campaign, date="2026-10-01", revenue="20.00",
            orders=1, spend="10.00", ctr=0.2, roas=2.0,
        )

    def generate(self):
        return self.client.post("/api/suggestions/generate/", {"campaign": self.campaign.id}, format="json")

    def test_generate_is_idempotent_for_open_suggestions(self):
        first = self.generate()
        self.assertEqual(first.status_code, 201, first.content)
        count = Suggestion.objects.filter(accepted=False).count()
        self.assertGreater(count, 0)
        second = self.generate()
        self.assertEqual(second.status_code, 201, second.content)
        self.assertEqual(Suggestion.objects.filter(accepted=False).count(), count)
        self.assertEqual(
            sorted(s["id"] for s in first.data),
            sorted(s["id"] for s in second.data),
        )

    def test_accept_creates_task_and_is_idempotent(self):
        suggestion = Suggestion.objects.create(
            campaign=self.campaign, kind="rule", title="Refresh creative", text="Test new hooks."
        )
        r = self.client.post(f"/api/suggestions/{suggestion.id}/accept/", {}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.data["created"])
        task = Task.objects.get(pk=r.data["task"]["id"])
        self.assertEqual(task.suggestion_id, suggestion.id)
        self.assertEqual(task.campaign_id, self.campaign.id)
        self.assertTrue(Suggestion.objects.get(pk=suggestion.id).accepted)

        again = self.client.post(f"/api/suggestions/{suggestion.id}/accept/", {}, format="json")
        self.assertEqual(again.status_code, 200, again.content)
        self.assertFalse(again.data["created"])
        self.assertEqual(Task.objects.filter(suggestion=suggestion).count(), 1)

    def test_accept_respects_due_date_and_rejects_garbage(self):
        suggestion = Suggestion.objects.create(campaign=self.campaign, kind="rule", title="Plan week")
        ok = self.client.post(
            f"/api/suggestions/{suggestion.id}/accept/", {"due_date": "2026-10-20"}, format="json"
        )
        self.assertEqual(ok.status_code, 200, ok.content)
        self.assertEqual(ok.data["task"]["due_date"], "2026-10-20")

        other = Suggestion.objects.create(campaign=self.campaign, kind="rule", title="Other")
        bad = self.client.post(
            f"/api/suggestions/{other.id}/accept/", {"due_date": "not-a-date"}, format="json"
        )
        self.assertEqual(bad.status_code, 400, bad.content)

    def test_reopen_moves_back_to_open(self):
        suggestion = Suggestion.objects.create(
            campaign=self.campaign, kind="rule", title="Hold steady", accepted=True
        )
        r = self.client.post(f"/api/suggestions/{suggestion.id}/reopen/", {}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertFalse(r.data["accepted"])

    def test_serializer_exposes_linked_task(self):
        suggestion = Suggestion.objects.create(campaign=self.campaign, kind="rule", title="Do it")
        Task.objects.create(campaign=self.campaign, title="Do it", suggestion=suggestion)
        r = self.client.get(f"/api/suggestions/{suggestion.id}/")
        self.assertEqual(r.status_code, 200)
        self.assertIsNotNone(r.data["task"])
        self.assertEqual(r.data["task"]["title"], "Do it")
