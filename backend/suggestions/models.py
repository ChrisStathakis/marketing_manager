from django.db import models


class Suggestion(models.Model):
    KIND_CHOICES = [("rule", "Rule"), ("ai", "AI")]

    campaign = models.ForeignKey("campaigns.Campaign", on_delete=models.CASCADE, related_name="suggestions")
    kind = models.CharField(max_length=10, choices=KIND_CHOICES, default="rule")
    title = models.CharField(max_length=255)
    text = models.TextField(blank=True)
    input_snapshot = models.JSONField(default=dict, blank=True)
    accepted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.kind}] {self.title}"
