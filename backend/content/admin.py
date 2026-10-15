from django.contrib import admin

from .models import ContentItem


@admin.register(ContentItem)
class ContentItemAdmin(admin.ModelAdmin):
    list_display = ["title", "campaign", "channel", "status", "publish_at"]
    list_filter = ["status", "channel"]
    search_fields = ["title", "copy"]
