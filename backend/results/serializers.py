from decimal import Decimal

from rest_framework import serializers

from campaigns.models import Campaign

from .models import DailyMetric


class DailyMetricSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyMetric
        fields = ["id", "campaign", "date", "revenue", "orders", "spend", "ctr", "roas", "source"]
        read_only_fields = ["source"]


class MetricImportRowSerializer(serializers.Serializer):
    """Row-level validation for /api/metrics/import-csv/."""

    campaign = serializers.PrimaryKeyRelatedField(queryset=Campaign.objects.all())
    date = serializers.DateField()
    revenue = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0, required=False, default=Decimal("0"))
    orders = serializers.IntegerField(min_value=0, required=False, default=0)
    spend = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0, required=False, default=Decimal("0"))
    ctr = serializers.FloatField(min_value=0, required=False, default=0.0)
    roas = serializers.FloatField(min_value=0, required=False)

    def validate(self, attrs):
        if attrs.get("roas") is None:
            spend = attrs.get("spend") or Decimal("0")
            revenue = attrs.get("revenue") or Decimal("0")
            attrs["roas"] = round(float(revenue / spend), 2) if spend else 0.0
        return attrs
