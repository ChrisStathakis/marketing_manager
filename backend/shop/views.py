from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import OrderRef, Product
from .serializers import OrderRefSerializer, ProductSerializer


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ["name", "external_id"]
    ordering_fields = ["name", "updated_at"]


class OrderRefViewSet(viewsets.ModelViewSet):
    queryset = OrderRef.objects.select_related("campaign").all()
    serializer_class = OrderRefSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["campaign", "utm_source", "utm_campaign"]
    ordering_fields = ["ordered_at", "total"]
