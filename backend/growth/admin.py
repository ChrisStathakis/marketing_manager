from django.contrib import admin

from .models import GrowthExperiment, PostPerformance, StatCard, TrafficSnapshot


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
