from django.contrib import admin

from .models import Suggestion


@admin.register(Suggestion)
class SuggestionAdmin(admin.ModelAdmin):
    list_display = ["title", "campaign", "kind", "accepted", "created_at"]
    list_filter = ["kind", "accepted"]
    search_fields = ["title", "text"]
