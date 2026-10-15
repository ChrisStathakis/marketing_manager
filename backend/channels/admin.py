from django.contrib import admin

from .models import Channel


@admin.register(Channel)
class ChannelAdmin(admin.ModelAdmin):
    list_display = ["name", "channel_type", "handle", "is_active"]
    list_filter = ["channel_type", "is_active"]
    search_fields = ["name", "handle"]
