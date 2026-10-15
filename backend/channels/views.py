from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import Channel
from .serializers import ChannelSerializer


class ChannelViewSet(viewsets.ModelViewSet):
    queryset = Channel.objects.all()
    serializer_class = ChannelSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["channel_type", "is_active"]
    search_fields = ["name", "handle"]
    ordering_fields = ["name"]
