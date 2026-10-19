from rest_framework import serializers

from .metrics import metric_label
from .models import GrowthExperiment, InstagramComment, InstagramTrackedPost, PostPerformance, StatCard, TrafficSnapshot
from .sources import platform_for_source


class StatCardSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = StatCard
        fields = [
            "id", "campaign", "kind", "format", "title", "subtitle",
            "payload", "image_url", "created_at",
        ]
        read_only_fields = ["id", "image_url", "created_at"]

    def get_image_url(self, obj):
        if not obj.image:
            return ""
        request = self.context.get("request")
        return request.build_absolute_uri(obj.image.url) if request else obj.image.url


class PostPerformanceSerializer(serializers.ModelSerializer):
    engagement_rate = serializers.FloatField(read_only=True)
    click_rate = serializers.FloatField(read_only=True)
    platform_label = serializers.CharField(source="get_platform_display", read_only=True)
    kind_label = serializers.CharField(source="get_kind_display", read_only=True)
    metric_label = serializers.SerializerMethodField()

    class Meta:
        model = PostPerformance
        fields = [
            "id", "campaign", "content_item", "platform", "platform_label",
            "kind", "kind_label", "metric_key", "metric_label",
            "url", "posted_at", "impressions", "engagements", "comments",
            "clicks", "engagement_rate", "click_rate", "notes", "created_at",
        ]
        read_only_fields = ["id", "engagement_rate", "click_rate", "created_at"]

    def get_metric_label(self, obj) -> str:
        return metric_label(obj.metric_key) if obj.metric_key else ""


class TrafficSnapshotSerializer(serializers.ModelSerializer):
    engagement_rate = serializers.FloatField(read_only=True)
    platform = serializers.SerializerMethodField()

    class Meta:
        model = TrafficSnapshot
        fields = [
            "id", "date", "source", "medium", "platform", "sessions",
            "engaged_sessions", "users", "views", "engagement_rate", "fetched_at",
        ]
        read_only_fields = fields

    def get_platform(self, obj) -> str | None:
        return platform_for_source(obj.source)


class GrowthExperimentSerializer(serializers.ModelSerializer):
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = GrowthExperiment
        fields = [
            "id", "name", "hypothesis", "metric", "status", "status_label",
            "result", "started_on", "ended_on", "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def validate(self, attrs):
        start = attrs.get("started_on", getattr(self.instance, "started_on", None))
        end = attrs.get("ended_on", getattr(self.instance, "ended_on", None))
        if start and end and end < start:
            raise serializers.ValidationError({"ended_on": "ended_on must be on or after started_on."})
        return attrs


class InstagramTrackedPostSerializer(serializers.ModelSerializer):
    comments_stored = serializers.IntegerField(read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = InstagramTrackedPost
        fields = [
            "id", "url", "shortcode", "media_pk", "owner_username", "caption",
            "comment_count", "comments_stored", "status", "status_label", "error",
            "last_scraped_at", "created_at",
        ]
        read_only_fields = fields


class InstagramCommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = InstagramComment
        fields = [
            "id", "post", "comment_pk", "author_username", "author_pk",
            "author_full_name", "text", "commented_at", "like_count",
            "child_count", "fetched_at",
        ]
        read_only_fields = fields
