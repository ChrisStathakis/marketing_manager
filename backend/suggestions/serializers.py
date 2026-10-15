from rest_framework import serializers

from .models import Suggestion


class SuggestionSerializer(serializers.ModelSerializer):
    task = serializers.SerializerMethodField()

    class Meta:
        model = Suggestion
        fields = ["id", "campaign", "kind", "title", "text", "input_snapshot", "accepted", "created_at", "task"]
        read_only_fields = ["id", "created_at", "task"]

    def get_task(self, obj):
        """The task this suggestion was converted into, if any."""
        task = obj.tasks.order_by("id").first()
        if task is None:
            return None
        return {"id": task.id, "title": task.title, "done": task.done, "due_date": task.due_date}
