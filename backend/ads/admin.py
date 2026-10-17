from django.contrib import admin

from .models import AdSpend


@admin.register(AdSpend)
class AdSpendAdmin(admin.ModelAdmin):
    list_display = ["campaign", "channel", "date", "spend", "clicks", "conversions", "source"]
    list_filter = ["date", "channel", "source"]
