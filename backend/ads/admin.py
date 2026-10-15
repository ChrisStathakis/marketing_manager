from django.contrib import admin

from .models import AdSpend


@admin.register(AdSpend)
class AdSpendAdmin(admin.ModelAdmin):
    list_display = ["campaign", "channel", "date", "spend", "clicks", "conversions"]
    list_filter = ["date", "channel"]
