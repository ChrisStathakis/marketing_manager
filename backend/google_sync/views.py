"""Sync endpoints for Google data sources.

Reads happen server-side (credentials never leave the backend) and write into
the regular metrics models, so the dashboard, results page and suggestions all
pick the data up without any changes.
"""
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from integrations.services import record_sync

from . import ga4, search_console
from .services import MAX_WINDOW_DAYS, PROVIDER, SyncNotConfigured, sync_ga4


def _requested_days(request):
    """Parsed ``days`` from the body, or None for the service default."""
    raw = request.data.get("days")
    if raw in (None, ""):
        return None, None
    try:
        days = int(raw)
    except (TypeError, ValueError):
        return None, "days must be an integer."
    if not 1 <= days <= MAX_WINDOW_DAYS:
        return None, f"days must be between 1 and {MAX_WINDOW_DAYS}."
    return days, None


@api_view(["POST"])
@permission_classes([IsAdminUser])
def sync_google_analytics(request):
    """Pull GA4 revenue/orders for the last N days into daily metrics."""
    days, error = _requested_days(request)
    if error:
        return Response({"detail": error}, status=status.HTTP_400_BAD_REQUEST)

    try:
        result = sync_ga4(days=days)
    except SyncNotConfigured as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except ga4.GA4Error as exc:
        record_sync(PROVIDER, error=str(exc))
        return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

    stored = record_sync(PROVIDER)
    return Response(
        {
            **result.as_dict(),
            "last_synced_at": timezone.now().isoformat() if stored else None,
        }
    )


@api_view(["POST"])
@permission_classes([IsAdminUser])
def sync_google_search_console(request):
    """Pull Google organic search totals, pages and queries into snapshots."""
    days, error = _requested_days(request)
    if error:
        return Response({"detail": error}, status=status.HTTP_400_BAD_REQUEST)

    # Imported lazily: the service writes growth models, while this app is
    # deliberately independent of the report layer.
    from growth.search_console import PROVIDER as GSC_PROVIDER
    from growth.search_console import sync_search_console

    try:
        result = sync_search_console(days=days)
    except SyncNotConfigured as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except search_console.SearchConsoleError as exc:
        record_sync(GSC_PROVIDER, error=str(exc))
        return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

    stored = record_sync(GSC_PROVIDER)
    return Response(
        {
            **result.as_dict(),
            "last_synced_at": timezone.now().isoformat() if stored else None,
        }
    )
