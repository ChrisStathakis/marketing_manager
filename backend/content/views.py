from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .filters import ContentItemFilter
from .models import ContentItem
from .serializers import ContentItemSerializer


class ContentItemViewSet(viewsets.ModelViewSet):
    queryset = ContentItem.objects.select_related("campaign", "channel").all()
    serializer_class = ContentItemSerializer
    permission_classes = [IsAuthenticated]
    filterset_class = ContentItemFilter
    search_fields = ["title", "copy"]
    ordering_fields = ["publish_at", "id"]
