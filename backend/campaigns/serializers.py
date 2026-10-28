from rest_framework import serializers
from .models import Campaign


class CampaignSerializer(serializers.ModelSerializer):
    playbook_name = serializers.CharField(source="playbook.name", read_only=True)

    class Meta:
        model = Campaign
        fields = [
            "id", "name", "objective", "budget", "status", "playbook", "playbook_name",
            "round_label", "locales", "platforms", "start_date", "end_date",
            "utm_campaign", "landing_path", "owner", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_locales(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("locales must be a list.")
        return [str(item) for item in value]

    def validate_platforms(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("platforms must be a list.")
        return [str(item) for item in value]

    def validate_landing_path(self, value):
        value = (value or "").strip()
        if value and not value.startswith("/"):
            value = f"/{value}"
        return value

    def validate(self, attrs):
        start = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start and end and end < start:
            raise serializers.ValidationError({"end_date": "end_date must be on or after start_date."})
        return attrs
