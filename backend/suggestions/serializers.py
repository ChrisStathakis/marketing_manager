from rest_framework import serializers
from .models import Suggestion


class SuggestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Suggestion
        fields = ["id", "campaign", "kind", "title", "text", "input_snapshot", "accepted", "created_at"]
        read_only_fields = ["id", "created_at"]
