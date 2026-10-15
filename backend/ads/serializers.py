from rest_framework import serializers
from .models import AdSpend


class AdSpendSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdSpend
        fields = ["id", "campaign", "channel", "date", "spend", "impressions", "clicks", "conversions"]
