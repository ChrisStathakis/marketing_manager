from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .filters import ContentItemFilter
from .models import ContentAsset, ContentItem
from .serializers import ContentAssetSerializer, ContentItemSerializer


class ContentItemViewSet(viewsets.ModelViewSet):
    queryset = ContentItem.objects.select_related("campaign", "channel", "card_set").prefetch_related("assets").all()
    serializer_class = ContentItemSerializer
    permission_classes = [IsAuthenticated]
    filterset_class = ContentItemFilter
    search_fields = ["title", "copy", "utm_content"]
    ordering_fields = ["publish_at", "id"]


class ContentAssetViewSet(viewsets.ModelViewSet):
    queryset = ContentAsset.objects.select_related("content_item").all()
    serializer_class = ContentAssetSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["content_item", "kind"]
    ordering_fields = ["position", "created_at"]
