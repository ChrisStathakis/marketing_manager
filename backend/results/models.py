from django.core.validators import MinValueValidator
from django.db import models


class DailyMetric(models.Model):
    SOURCE_MANUAL = "manual"
    SOURCE_GA4 = "ga4"
    SOURCE_GOOGLE_ADS = "google_ads"
    SOURCE_CHOICES = [
        (SOURCE_MANUAL, "Manual"),
        (SOURCE_GA4, "Google Analytics 4"),
        (SOURCE_GOOGLE_ADS, "Google Ads"),
    ]

    campaign = models.ForeignKey("campaigns.Campaign", on_delete=models.CASCADE, related_name="daily_metrics")
    date = models.DateField()
    revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    orders = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    spend = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    ctr = models.FloatField(default=0, validators=[MinValueValidator(0)])
    roas = models.FloatField(default=0, validators=[MinValueValidator(0)])
    # Where the row came from; syncs only touch their own numbers, and a CSV
    # import always marks the row manual again.
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default=SOURCE_MANUAL)

    class Meta:
        ordering = ["-date"]
        unique_together = [("campaign", "date")]

    def __str__(self):
        return f"{self.campaign_id} {self.date} rev={self.revenue}"
