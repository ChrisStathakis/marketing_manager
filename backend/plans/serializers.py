from rest_framework import serializers
from .models import Task


class TaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = ["id", "campaign", "title", "notes", "due_date", "done", "suggestion", "created_at"]
        read_only_fields = ["id", "created_at"]
