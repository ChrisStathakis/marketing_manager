from decimal import Decimal

from rest_framework import serializers

from campaigns.models import Campaign
from channels.models import Channel

from .models import AdSpend


class AdSpendSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdSpend
        fields = ["id", "campaign", "channel", "date", "spend", "impressions", "clicks", "conversions"]

    def validate(self, attrs):
        # The DB unique_together does not catch duplicates when channel is
        # NULL (SQL treats NULLs as distinct), so enforce it here.
        campaign = attrs.get("campaign", getattr(self.instance, "campaign", None))
        channel = attrs.get("channel", getattr(self.instance, "channel", None))
        date = attrs.get("date", getattr(self.instance, "date", None))
        if campaign is None or date is None:
            return attrs
        duplicates = AdSpend.objects.filter(campaign=campaign, date=date)
        duplicates = duplicates.filter(channel__isnull=True) if channel is None else duplicates.filter(channel=channel)
        if self.instance is not None:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise serializers.ValidationError(
                {"detail": "A spend row already exists for this campaign/channel/date."}
            )
        return attrs


class AdSpendImportRowSerializer(serializers.Serializer):
    """Row-level validation for /api/spend/import-csv/."""

    campaign = serializers.PrimaryKeyRelatedField(queryset=Campaign.objects.all())
    channel = serializers.PrimaryKeyRelatedField(queryset=Channel.objects.all(), required=False, allow_null=True)
    date = serializers.DateField()
    spend = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0, required=False, default=Decimal("0"))
    impressions = serializers.IntegerField(min_value=0, required=False, default=0)
    clicks = serializers.IntegerField(min_value=0, required=False, default=0)
    conversions = serializers.IntegerField(min_value=0, required=False, default=0)
