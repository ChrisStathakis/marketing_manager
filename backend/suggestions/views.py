from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from campaigns.models import Campaign
from plans.serializers import TaskSerializer

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
            # Refresh an open suggestion with the same title instead of stacking dupes.
            obj = Suggestion.objects.filter(
                campaign=campaign, kind="rule", title=s["title"], accepted=False
            ).first()
            if obj:
                obj.text = s["text"]
                obj.input_snapshot = s["input_snapshot"]
                obj.save(update_fields=["text", "input_snapshot"])
            else:
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
                {"detail": str(exc), "hint": "Add a key in Settings → API keys (or set OPENAI_API_KEY in backend/.env); rule suggestions still work at /api/suggestions/generate/."},
                status=status.HTTP_501_NOT_IMPLEMENTED,
            )
        except Exception as exc:
            return Response({"detail": f"LLM call failed: {exc}"}, status=status.HTTP_502_BAD_GATEWAY)
        obj = Suggestion.objects.filter(campaign=campaign, kind="ai", accepted=False).first()
        if obj:
            obj.text = result["text"]
            obj.input_snapshot = result["snapshot"]
            obj.save(update_fields=["text", "input_snapshot"])
            return Response(SuggestionSerializer(obj).data)
        obj = Suggestion.objects.create(
            campaign=campaign, kind="ai", title="AI next steps",
            text=result["text"], input_snapshot=result["snapshot"],
        )
        return Response(SuggestionSerializer(obj).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def accept(self, request, pk=None):
        """Mark accepted and turn it into a task (idempotent)."""
        suggestion = self.get_object()
        task = suggestion.tasks.order_by("id").first()
        created = False
        if task is None:
            ser = TaskSerializer(
                data={
                    "campaign": suggestion.campaign_id,
                    "title": request.data.get("title") or suggestion.title,
                    "notes": suggestion.text,
                    "due_date": request.data.get("due_date") or None,
                    "suggestion": suggestion.id,
                }
            )
            ser.is_valid(raise_exception=True)
            task = ser.save()
            created = True
        if not suggestion.accepted:
            suggestion.accepted = True
            suggestion.save(update_fields=["accepted"])
        return Response(
            {
                "suggestion": SuggestionSerializer(suggestion).data,
                "task": TaskSerializer(task).data,
                "created": created,
            }
        )

    @action(detail=True, methods=["post"])
    def reopen(self, request, pk=None):
        """Move a suggestion back to the open list (keeps any created task)."""
        suggestion = self.get_object()
        if suggestion.accepted:
            suggestion.accepted = False
            suggestion.save(update_fields=["accepted"])
        return Response(SuggestionSerializer(suggestion).data)
