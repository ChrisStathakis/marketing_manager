from django.conf import settings
from django.db import connection
from django.db.models import Sum
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from campaigns.models import Campaign
from results.models import DailyMetric


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def summary(request):
    totals = DailyMetric.objects.aggregate(
        spend=Sum("spend"), revenue=Sum("revenue"), orders=Sum("orders"),
    )
    spend = float(totals["spend"] or 0)
    revenue = float(totals["revenue"] or 0)
    per_campaign = list(
        Campaign.objects.values("id", "name", "status").annotate(
            spend=Sum("daily_metrics__spend"),
            revenue=Sum("daily_metrics__revenue"),
            orders=Sum("daily_metrics__orders"),
        ).order_by("-daily_metrics__revenue")[:20]
    )
    for row in per_campaign:
        row["spend"] = float(row["spend"] or 0)
        row["revenue"] = float(row["revenue"] or 0)
        row["orders"] = row["orders"] or 0
        row["roas"] = round(row["revenue"] / row["spend"], 2) if row["spend"] else 0
    return Response({
        "spend": spend,
        "revenue": revenue,
        "orders": totals["orders"] or 0,
        "roas": round(revenue / spend, 2) if spend else 0,
        "campaigns": per_campaign,
    })


@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:
        return Response({"ok": False, "database": False}, status=503)
    return Response({"ok": True, "database": True})


@api_view(["GET"])
@permission_classes([AllowAny])
def public_config(request):
    """Non-secret runtime flags the frontend needs before login."""
    return Response({"registration_enabled": settings.ALLOW_REGISTRATION})
