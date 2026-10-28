from rest_framework import serializers

from .metrics import metric_label
from .models import (
    Boost,
    CardSet,
    GrowthExperiment,
    HashtagSet,
    InstagramComment,
    InstagramTrackedPost,
    KpiTarget,
    Playbook,
    PlaybookSlot,
    PostPerformance,
    StatCard,
    TrafficSnapshot,
)
from .sources import platform_for_source


class StatCardSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = StatCard
        fields = [
            "id", "campaign", "card_set", "position", "kind", "format", "title", "subtitle",
            "payload", "image_url", "created_at",
        ]
        read_only_fields = ["id", "image_url", "created_at"]

    def get_image_url(self, obj):
        if not obj.image:
            return ""
        request = self.context.get("request")
        return request.build_absolute_uri(obj.image.url) if request else obj.image.url


class PlaybookSlotSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlaybookSlot
        fields = [
            "id", "playbook", "order", "day_offset", "time", "platform", "format",
            "content_kind", "locales", "title_template", "brief",
            "utm_content_template", "asset_required", "paid_budget",
            "is_task_only", "notes",
        ]
        read_only_fields = ["id", "playbook"]
        extra_kwargs = {"time": {"required": False}}

    def validate_locales(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("locales must be a list of language codes.")
        return [str(item) for item in value]


class PlaybookSerializer(serializers.ModelSerializer):
    slots = PlaybookSlotSerializer(many=True, required=False)
    slot_count = serializers.IntegerField(source="slots.count", read_only=True)

    class Meta:
        model = Playbook
        fields = [
            "id", "name", "description", "default_locales", "default_platforms",
            "is_seeded", "slot_count", "slots", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "is_seeded", "slot_count", "created_at", "updated_at"]

    def validate_default_locales(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("default_locales must be a list.")
        return [str(item) for item in value]

    def validate_default_platforms(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("default_platforms must be a list.")
        return [str(item) for item in value]

    def create(self, validated_data):
        slots = validated_data.pop("slots", [])
        playbook = Playbook.objects.create(**validated_data)
        for index, slot in enumerate(slots):
            slot.pop("playbook", None)
            slot.setdefault("order", index)
            PlaybookSlot.objects.create(playbook=playbook, **slot)
        return playbook

    def update(self, instance, validated_data):
        slots = validated_data.pop("slots", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if slots is not None:
            instance.slots.all().delete()
            for index, slot in enumerate(slots):
                slot.pop("playbook", None)
                slot.setdefault("order", index)
                PlaybookSlot.objects.create(playbook=instance, **slot)
        return instance


class CardSetSerializer(serializers.ModelSerializer):
    slides = serializers.SerializerMethodField()

    class Meta:
        model = CardSet
        fields = ["id", "campaign", "kind", "format", "title", "subtitle", "payload", "slides", "created_at"]
        read_only_fields = ["id", "slides", "created_at"]

    def get_slides(self, obj):
        rows = obj.slides.order_by("position", "id")
        return StatCardSerializer(rows, many=True, context=self.context).data


class KpiTargetSerializer(serializers.ModelSerializer):
    metric_label = serializers.CharField(source="get_metric_display", read_only=True)

    class Meta:
        model = KpiTarget
        fields = [
            "id", "campaign", "metric", "metric_label", "target", "window_start",
            "window_end", "notes", "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def validate(self, attrs):
        start = attrs.get("window_start", getattr(self.instance, "window_start", None))
        end = attrs.get("window_end", getattr(self.instance, "window_end", None))
        if start and end and end < start:
            raise serializers.ValidationError({"window_end": "window_end must be on or after window_start."})
        return attrs


class BoostSerializer(serializers.ModelSerializer):
    platform_label = serializers.CharField(source="get_platform_display", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Boost
        fields = [
            "id", "campaign", "content_item", "platform", "platform_label", "status",
            "status_label", "objective", "daily_budget", "total_budget", "start_date",
            "end_date", "targeting", "cpa_target", "notes", "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def validate(self, attrs):
        start = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start and end and end < start:
            raise serializers.ValidationError({"end_date": "end_date must be on or after start_date."})
        return attrs


class HashtagSetSerializer(serializers.ModelSerializer):
    class Meta:
        model = HashtagSet
        fields = ["id", "name", "locale", "platform", "tags", "is_default", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate_tags(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("tags must be a list.")
        return [str(item) for item in value]


class PostPerformanceSerializer(serializers.ModelSerializer):
    engagement_rate = serializers.FloatField(read_only=True)
    click_rate = serializers.FloatField(read_only=True)
    save_rate = serializers.FloatField(read_only=True)
    share_rate = serializers.FloatField(read_only=True)
    platform_label = serializers.CharField(source="get_platform_display", read_only=True)
    kind_label = serializers.CharField(source="get_kind_display", read_only=True)
    format_label = serializers.CharField(source="get_format_display", read_only=True)
    locale_label = serializers.CharField(source="get_locale_display", read_only=True)
    metric_label = serializers.SerializerMethodField()

    class Meta:
        model = PostPerformance
        fields = [
            "id", "campaign", "content_item", "platform", "platform_label",
            "kind", "kind_label", "metric_key", "metric_label", "format", "format_label",
            "locale", "locale_label", "utm_content", "url", "posted_at",
            "impressions", "reach", "engagements", "saves", "shares", "comments",
            "profile_visits", "clicks", "signups", "upvote_ratio",
            "engagement_rate", "click_rate", "save_rate", "share_rate", "notes", "created_at",
        ]
        read_only_fields = [
            "id", "engagement_rate", "click_rate", "save_rate", "share_rate", "created_at",
        ]

    def get_metric_label(self, obj) -> str:
        return metric_label(obj.metric_key) if obj.metric_key else ""


class TrafficSnapshotSerializer(serializers.ModelSerializer):
    engagement_rate = serializers.FloatField(read_only=True)
    platform = serializers.SerializerMethodField()

    class Meta:
        model = TrafficSnapshot
        fields = [
            "id", "date", "source", "medium", "campaign", "content", "platform",
            "sessions", "engaged_sessions", "users", "views", "engagement_rate", "fetched_at",
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
