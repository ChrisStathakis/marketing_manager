from django.core.validators import MinValueValidator
from django.db import models


class DailyMetric(models.Model):
    campaign = models.ForeignKey("campaigns.Campaign", on_delete=models.CASCADE, related_name="daily_metrics")
    date = models.DateField()
    revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    orders = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    spend = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    ctr = models.FloatField(default=0, validators=[MinValueValidator(0)])
    roas = models.FloatField(default=0, validators=[MinValueValidator(0)])

    class Meta:
        ordering = ["-date"]
        unique_together = [("campaign", "date")]

    def __str__(self):
        return f"{self.campaign_id} {self.date} rev={self.revenue}"
