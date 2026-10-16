"""Integration credential API.

Read: any authenticated user (status + documentation, never key values).
Write: staff/admin only (write-only key — the value is never returned).
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response

from .registry import INTEGRATIONS, get_integration
from .services import credential_status, delete_credential, set_credential

MIN_KEY_LENGTH = 16


def _payload(integration: dict) -> dict:
    """Registry metadata + live status. Contains no secret values."""
    return {**integration, **credential_status(integration["id"])}


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def integration_list(request):
    return Response([_payload(item) for item in INTEGRATIONS])


@api_view(["PUT", "DELETE"])
@permission_classes([IsAdminUser])
def integration_detail(request, provider):
    integration = get_integration(provider)
    if integration is None:
        return Response({"detail": "Unknown integration."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "DELETE":
        delete_credential(provider)
        return Response(_payload(integration))

    raw_key = (request.data.get("key") or "").strip()
    if len(raw_key) < MIN_KEY_LENGTH:
        return Response(
            {"detail": f"key must be at least {MIN_KEY_LENGTH} characters."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    set_credential(provider, raw_key, user=request.user)
    return Response(_payload(integration))
