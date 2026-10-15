from django.contrib import admin

from .models import Campaign


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ["name", "status", "budget", "start_date", "end_date", "owner"]
    list_filter = ["status"]
    search_fields = ["name", "objective", "utm_campaign"]
