from django.contrib import admin

from .models import OrderRef, Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ["name", "external_id", "price"]
    search_fields = ["name", "external_id"]


@admin.register(OrderRef)
class OrderRefAdmin(admin.ModelAdmin):
    list_display = ["external_id", "campaign", "total", "ordered_at"]
    list_filter = ["utm_source", "utm_campaign"]
