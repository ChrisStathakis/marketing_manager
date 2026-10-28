from rest_framework import serializers

from .models import ContentAsset, ContentItem


class ContentAssetSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = ContentAsset
        fields = ["id", "content_item", "kind", "file", "file_url", "url", "position", "alt_text", "created_at"]
        read_only_fields = ["id", "file_url", "created_at"]

    def get_file_url(self, obj):
        if not obj.file:
            return ""
        request = self.context.get("request")
        return request.build_absolute_uri(obj.file.url) if request else obj.file.url

    def validate(self, attrs):
        file = attrs.get("file", getattr(self.instance, "file", None))
        url = attrs.get("url", getattr(self.instance, "url", ""))
        if not file and not url:
            raise serializers.ValidationError("Provide a file or a URL.")
        return attrs


class ContentItemSerializer(serializers.ModelSerializer):
    assets = ContentAssetSerializer(many=True, read_only=True)
    locale_label = serializers.CharField(source="get_locale_display", read_only=True)
    format_label = serializers.CharField(source="get_format_display", read_only=True)

    class Meta:
        model = ContentItem
        fields = [
            "id", "campaign", "channel", "card_set", "title", "copy", "asset_url",
            "link", "utm_source", "utm_medium", "utm_campaign", "utm_content",
            "locale", "locale_label", "format", "format_label", "content_kind",
            "thread", "notes", "publish_at", "status", "assets",
        ]
        read_only_fields = ["id", "assets"]

    def validate_thread(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("thread must be a list of tweets.")
        return [str(item) for item in value]
