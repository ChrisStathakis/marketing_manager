from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import Campaign
from .serializers import CampaignSerializer


class CampaignViewSet(viewsets.ModelViewSet):
    queryset = Campaign.objects.all()
    serializer_class = CampaignSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["status", "owner"]
    search_fields = ["name", "objective", "utm_campaign"]
    ordering_fields = ["created_at", "start_date", "budget", "name"]

    def perform_create(self, serializer):
        if not serializer.validated_data.get("owner"):
            serializer.save(owner=self.request.user)
        else:
            serializer.save()
