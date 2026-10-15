from rest_framework import serializers
from .models import ContentItem


class ContentItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContentItem
        fields = [
            "id", "campaign", "channel", "title", "copy", "asset_url",
            "link", "utm_source", "utm_medium", "utm_campaign",
            "publish_at", "status",
        ]
