from datetime import timedelta

from django.db import connection
from django.db.models import Q, Sum
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from campaigns.models import Campaign
from config.registration import registration_open, users_exist
from results.models import DailyMetric


def _parse_range(request):
    """Date range from ?days=N or ?date__gte=&date__lte= (either may be absent)."""
    start = parse_date(request.query_params.get("date__gte", ""))
    end = parse_date(request.query_params.get("date__lte", ""))
    days = request.query_params.get("days")
    if days and not start:
        try:
            count = max(1, min(int(days), 3650))
        except ValueError:
            count = 30
        end = end or timezone.localdate()
        start = end - timedelta(days=count - 1)
    return start, end


def _totals(queryset):
    totals = queryset.aggregate(spend=Sum("spend"), revenue=Sum("revenue"), orders=Sum("orders"))
    spend = float(totals["spend"] or 0)
    revenue = float(totals["revenue"] or 0)
    return {
        "spend": spend,
        "revenue": revenue,
        "orders": totals["orders"] or 0,
        "roas": round(revenue / spend, 2) if spend else 0.0,
    }


def _delta(current, previous):
    if not previous:
        return None
    return round((current - previous) / previous * 100, 1)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def summary(request):
    start, end = _parse_range(request)

    metrics = DailyMetric.objects.all()
    if start:
        metrics = metrics.filter(date__gte=start)
    if end:
        metrics = metrics.filter(date__lte=end)
    totals = _totals(metrics)

    # Same-length window immediately before the selected one, for deltas.
    deltas = {"spend": None, "revenue": None, "orders": None, "roas": None}
    if start and end:
        length = (end - start).days + 1
        prev_end = start - timedelta(days=1)
        prev_start = prev_end - timedelta(days=length - 1)
        previous = _totals(DailyMetric.objects.filter(date__gte=prev_start, date__lte=prev_end))
        deltas = {key: _delta(totals[key], previous[key]) for key in deltas}

    series = [
        {
            "date": row["date"].isoformat(),
            "revenue": float(row["revenue"] or 0),
            "spend": float(row["spend"] or 0),
            "orders": row["orders"] or 0,
        }
        for row in metrics.values("date")
        .annotate(revenue=Sum("revenue"), spend=Sum("spend"), orders=Sum("orders"))
        .order_by("date")
    ]

    metric_q = Q()
    if start:
        metric_q &= Q(daily_metrics__date__gte=start)
    if end:
        metric_q &= Q(daily_metrics__date__lte=end)
    per_campaign = list(
        Campaign.objects.values("id", "name", "status")
        .annotate(
            spend=Sum("daily_metrics__spend", filter=metric_q),
            revenue=Sum("daily_metrics__revenue", filter=metric_q),
            orders=Sum("daily_metrics__orders", filter=metric_q),
        )
        .order_by("-revenue")[:20]
    )
    for row in per_campaign:
        row["spend"] = float(row["spend"] or 0)
        row["revenue"] = float(row["revenue"] or 0)
        row["orders"] = row["orders"] or 0
        row["roas"] = round(row["revenue"] / row["spend"], 2) if row["spend"] else 0

    return Response(
        {
            **totals,
            "deltas": deltas,
            "series": series,
            "range": {
                "start": start.isoformat() if start else None,
                "end": end.isoformat() if end else None,
            },
            "campaigns": per_campaign,
        }
    )


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
    return Response({"registration_enabled": registration_open(), "users_exist": users_exist()})
