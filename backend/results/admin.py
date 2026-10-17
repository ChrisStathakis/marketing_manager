from django.contrib import admin

from .models import DailyMetric


@admin.register(DailyMetric)
class DailyMetricAdmin(admin.ModelAdmin):
    list_display = ["campaign", "date", "revenue", "orders", "spend", "roas", "source"]
    list_filter = ["date", "source"]
