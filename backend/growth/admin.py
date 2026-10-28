from django.contrib import admin

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
    SearchConsoleSnapshot,
    StatCard,
    TrafficSnapshot,
)


class PlaybookSlotInline(admin.TabularInline):
    model = PlaybookSlot
    extra = 0
    fields = ("order", "day_offset", "time", "platform", "format", "content_kind", "locales", "title_template", "is_task_only")
    ordering = ("order",)


@admin.register(Playbook)
class PlaybookAdmin(admin.ModelAdmin):
    list_display = ("name", "is_seeded", "slot_count", "updated_at")
    search_fields = ("name", "description")
    inlines = [PlaybookSlotInline]

    def slot_count(self, obj):
        return obj.slots.count()


@admin.register(CardSet)
class CardSetAdmin(admin.ModelAdmin):
    list_display = ("title", "kind", "format", "campaign", "created_at")
    list_filter = ("kind", "format")


@admin.register(KpiTarget)
class KpiTargetAdmin(admin.ModelAdmin):
    list_display = ("campaign", "metric", "target", "window_start", "window_end")
    list_filter = ("metric",)


@admin.register(Boost)
class BoostAdmin(admin.ModelAdmin):
    list_display = ("platform", "status", "campaign", "total_budget", "start_date", "end_date")
    list_filter = ("platform", "status")


@admin.register(HashtagSet)
class HashtagSetAdmin(admin.ModelAdmin):
    list_display = ("name", "locale", "platform", "is_default")
    list_filter = ("locale", "platform", "is_default")


@admin.register(StatCard)
class StatCardAdmin(admin.ModelAdmin):
    list_display = ("title", "kind", "format", "campaign", "created_at")
    list_filter = ("kind", "format")
    search_fields = ("title", "subtitle")


@admin.register(PostPerformance)
class PostPerformanceAdmin(admin.ModelAdmin):
    list_display = ("platform", "kind", "metric_key", "posted_at", "impressions", "engagements", "clicks", "campaign")
    list_filter = ("platform", "kind")
    date_hierarchy = "posted_at"
    search_fields = ("url", "notes", "metric_key")


@admin.register(GrowthExperiment)
class GrowthExperimentAdmin(admin.ModelAdmin):
    list_display = ("name", "status", "metric", "started_on", "ended_on")
    list_filter = ("status",)
    search_fields = ("name", "hypothesis", "result")


@admin.register(TrafficSnapshot)
class TrafficSnapshotAdmin(admin.ModelAdmin):
    list_display = ("date", "source", "medium", "sessions", "engaged_sessions", "users", "views")
    list_filter = ("source", "medium")
    date_hierarchy = "date"
    search_fields = ("source", "medium")


@admin.register(SearchConsoleSnapshot)
class SearchConsoleSnapshotAdmin(admin.ModelAdmin):
    list_display = ("date", "site_url", "scope", "page_path", "query", "clicks", "impressions")
    list_filter = ("scope", "site_url")
    date_hierarchy = "date"
    search_fields = ("page_path", "page_url", "query")


class InstagramCommentInline(admin.TabularInline):
    model = InstagramComment
    extra = 0
    fields = ("author_username", "text", "like_count", "commented_at")
    readonly_fields = ("author_username", "text", "like_count", "commented_at")
    can_delete = False
    show_change_link = False


@admin.register(InstagramTrackedPost)
class InstagramTrackedPostAdmin(admin.ModelAdmin):
    list_display = ("shortcode", "owner_username", "comment_count", "status", "last_scraped_at", "created_at")
    list_filter = ("status",)
    search_fields = ("shortcode", "url", "owner_username")
    date_hierarchy = "created_at"
    inlines = [InstagramCommentInline]


@admin.register(InstagramComment)
class InstagramCommentAdmin(admin.ModelAdmin):
    list_display = ("author_username", "post", "like_count", "commented_at", "fetched_at")
    list_filter = ("post",)
    search_fields = ("author_username", "author_full_name", "text")
    date_hierarchy = "commented_at"
