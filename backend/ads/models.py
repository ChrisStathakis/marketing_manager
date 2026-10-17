from django.core.validators import MinValueValidator
from django.db import models


class AdSpend(models.Model):
    SOURCE_MANUAL = "manual"
    SOURCE_GA4 = "ga4"
    SOURCE_GOOGLE_ADS = "google_ads"
    SOURCE_CHOICES = [
        (SOURCE_MANUAL, "Manual"),
        (SOURCE_GA4, "Google Analytics 4"),
        (SOURCE_GOOGLE_ADS, "Google Ads"),
    ]

    campaign = models.ForeignKey("campaigns.Campaign", on_delete=models.CASCADE, related_name="ad_spends")
    channel = models.ForeignKey("channels.Channel", null=True, blank=True, on_delete=models.SET_NULL, related_name="ad_spends")
    date = models.DateField()
    spend = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    impressions = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    clicks = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    conversions = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    # See DailyMetric.source — a CSV import always marks the row manual again.
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default=SOURCE_MANUAL)

    class Meta:
        ordering = ["-date"]
        unique_together = [("campaign", "channel", "date")]

    def __str__(self):
        return f"{self.campaign_id} {self.channel_id} {self.date} spend={self.spend}"
