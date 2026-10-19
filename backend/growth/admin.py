from django.contrib import admin

from .models import (
    GrowthExperiment,
    InstagramComment,
    InstagramTrackedPost,
    PostPerformance,
    StatCard,
    TrafficSnapshot,
)


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
