from uuid import uuid4

from django.db import models
from django.utils import timezone


def asset_upload_path(instance, filename):
    stamp = timezone.now()
    extension = (filename.rsplit(".", 1)[-1] or "bin").lower()
    return f"content/assets/{stamp:%Y/%m}/{uuid4().hex}.{extension}"


class ContentItem(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("scheduled", "Scheduled"),
        ("published", "Published"),
    ]
    FORMAT_CHOICES = [
        ("post", "Feed post"),
        ("carousel", "Carousel"),
        ("reel", "Reel / short video"),
        ("story", "Story"),
        ("thread", "Thread"),
        ("photo_carousel", "Photo carousel"),
        ("short", "Short video"),
        ("text_post", "Text post"),
        ("video", "Video"),
        ("other", "Other"),
    ]
    LOCALE_CHOICES = [
        ("en", "English"),
        ("el", "Greek"),
        ("tr", "Turkish"),
        ("sr", "Serbian"),
        ("lt", "Lithuanian"),
    ]

    campaign = models.ForeignKey("campaigns.Campaign", on_delete=models.CASCADE, related_name="items")
    channel = models.ForeignKey("channels.Channel", null=True, blank=True, on_delete=models.SET_NULL, related_name="content_items")
    card_set = models.ForeignKey(
        "growth.CardSet", null=True, blank=True, on_delete=models.SET_NULL, related_name="content_items"
    )
    title = models.CharField(max_length=255)
    copy = models.TextField(blank=True)
    asset_url = models.URLField(blank=True)
    link = models.URLField(blank=True)
    utm_source = models.CharField(max_length=255, blank=True)
    utm_medium = models.CharField(max_length=255, blank=True)
    utm_campaign = models.CharField(max_length=255, blank=True)
    utm_content = models.CharField(max_length=255, blank=True)
    locale = models.CharField(max_length=8, choices=LOCALE_CHOICES, blank=True)
    format = models.CharField(max_length=20, choices=FORMAT_CHOICES, blank=True)
    content_kind = models.CharField(max_length=20, blank=True)
    thread = models.JSONField(default=list, blank=True, help_text="Ordered X/Twitter thread tweets.")
    notes = models.TextField(blank=True)
    publish_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")

    class Meta:
        ordering = ["-publish_at", "-id"]
        indexes = [
            models.Index(fields=["publish_at"]),
            models.Index(fields=["locale"]),
            models.Index(fields=["format"]),
        ]

    def __str__(self):
        return self.title


class ContentAsset(models.Model):
    """A rendered slide or a video cut that belongs to one calendar entry."""

    KIND_CHOICES = [
        ("image", "Image"),
        ("video", "Video"),
        ("link", "Link"),
        ("other", "Other"),
    ]

    content_item = models.ForeignKey(ContentItem, on_delete=models.CASCADE, related_name="assets")
    kind = models.CharField(max_length=10, choices=KIND_CHOICES, default="image")
    file = models.FileField(upload_to=asset_upload_path, blank=True)
    url = models.URLField(blank=True)
    position = models.PositiveIntegerField(default=0)
    alt_text = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["position", "id"]

    def __str__(self):
        return f"{self.content_item} · {self.get_kind_display()} {self.position}"
