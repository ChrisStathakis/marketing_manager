from django.contrib import admin

from .models import Task


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ["title", "campaign", "due_date", "done"]
    list_filter = ["done"]
    search_fields = ["title"]
