from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from campaigns.models import Campaign
from .models import Suggestion
from .serializers import SuggestionSerializer
from .services import llm_suggestions, rule_suggestions


class SuggestionViewSet(viewsets.ModelViewSet):
    queryset = Suggestion.objects.select_related("campaign").all()
    serializer_class = SuggestionSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["campaign", "kind", "accepted"]
    ordering_fields = ["created_at"]

    @action(detail=False, methods=["post"], url_path="generate")
    def generate(self, request):
        campaign_id = request.data.get("campaign")
        try:
            campaign = Campaign.objects.get(pk=campaign_id)
        except (Campaign.DoesNotExist, TypeError, ValueError):
            return Response({"detail": "valid campaign id required."}, status=status.HTTP_400_BAD_REQUEST)
        made = []
        for s in rule_suggestions(campaign):
            obj = Suggestion.objects.create(
                campaign=campaign, kind="rule", title=s["title"],
                text=s["text"], input_snapshot=s["input_snapshot"],
            )
            made.append(obj)
        return Response(SuggestionSerializer(made, many=True).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"], url_path="generate-ai")
    def generate_ai(self, request):
        campaign_id = request.data.get("campaign")
        try:
            campaign = Campaign.objects.get(pk=campaign_id)
        except (Campaign.DoesNotExist, TypeError, ValueError):
            return Response({"detail": "valid campaign id required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            result = llm_suggestions(campaign, api_key=request.data.get("api_key"))
        except RuntimeError as exc:
            return Response(
                {"detail": str(exc), "hint": "Set OPENAI_API_KEY env or pass api_key; rule suggestions still available at /api/suggestions/generate/."},
                status=status.HTTP_501_NOT_IMPLEMENTED,
            )
        except Exception as exc:
            return Response({"detail": f"LLM call failed: {exc}"}, status=status.HTTP_502_BAD_GATEWAY)
        obj = Suggestion.objects.create(
            campaign=campaign, kind="ai", title="AI next steps",
            text=result["text"], input_snapshot=result["snapshot"],
        )
        return Response(SuggestionSerializer(obj).data, status=status.HTTP_201_CREATED)
