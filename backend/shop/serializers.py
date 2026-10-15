from rest_framework import serializers
from .models import OrderRef, Product


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ["id", "external_id", "name", "price", "url", "updated_at"]
        read_only_fields = ["id", "updated_at"]


class OrderRefSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderRef
        fields = ["id", "external_id", "campaign", "utm_source", "utm_medium", "utm_campaign", "total", "ordered_at"]
