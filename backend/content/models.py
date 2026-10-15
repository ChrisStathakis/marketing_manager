from django.db import models


class ContentItem(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("scheduled", "Scheduled"),
        ("published", "Published"),
    ]

    campaign = models.ForeignKey("campaigns.Campaign", on_delete=models.CASCADE, related_name="items")
    channel = models.ForeignKey("channels.Channel", null=True, blank=True, on_delete=models.SET_NULL, related_name="content_items")
    title = models.CharField(max_length=255)
    copy = models.TextField(blank=True)
    asset_url = models.URLField(blank=True)
    link = models.URLField(blank=True)
    utm_source = models.CharField(max_length=255, blank=True)
    utm_medium = models.CharField(max_length=255, blank=True)
    utm_campaign = models.CharField(max_length=255, blank=True)
    publish_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")

    class Meta:
        ordering = ["-publish_at", "-id"]

    def __str__(self):
        return self.title
