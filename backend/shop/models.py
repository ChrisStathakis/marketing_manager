from django.core.validators import MinValueValidator
from django.db import models


class Product(models.Model):
    external_id = models.CharField(max_length=255, unique=True)
    name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    url = models.URLField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.external_id})"


class OrderRef(models.Model):
    external_id = models.CharField(max_length=255, unique=True)
    campaign = models.ForeignKey("campaigns.Campaign", null=True, blank=True, on_delete=models.SET_NULL, related_name="orders")
    utm_source = models.CharField(max_length=255, blank=True)
    utm_medium = models.CharField(max_length=255, blank=True)
    utm_campaign = models.CharField(max_length=255, blank=True)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    ordered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-ordered_at", "-id"]

    def __str__(self):
        return f"Order {self.external_id} total={self.total}"
