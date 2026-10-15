from django.db import models


class Channel(models.Model):
    TYPE_CHOICES = [
        ("facebook", "Facebook"),
        ("instagram", "Instagram"),
        ("tiktok", "TikTok"),
        ("google", "Google"),
        ("x", "X"),
        ("other", "Other"),
    ]

    name = models.CharField(max_length=255)
    channel_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="other")
    handle = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.channel_type})"
