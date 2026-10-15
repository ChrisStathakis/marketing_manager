from rest_framework import serializers
from .models import DailyMetric


class DailyMetricSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyMetric
        fields = ["id", "campaign", "date", "revenue", "orders", "spend", "ctr", "roas"]
