"""Integration credential API.

Read: any authenticated user (status + documentation, never key values).
Write: staff/admin only (write-only secrets — values are never returned).

A write accepts either the classic single-key shape ``{"key": "…"}`` or the
generic ``{"fields": {…}, "config": {…}}``; see ``registry.py`` for the field
specs of each integration.

Secrets merge (an omitted field keeps its stored value, so settings can change
without re-pasting a key); ``config`` is a full replacement, because the UI
always sends the current values back.
"""
import os

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response

from .registry import INTEGRATIONS, config_fields, get_integration, secret_fields
from .services import (
    credential_status,
    delete_credential,
    get_credential_secrets,
    set_credential,
)


def _payload(integration: dict) -> dict:
    """Registry metadata + live status. Contains no secret values."""
    return {**integration, **credential_status(integration["id"])}


def _requested_secrets(data: dict, fields: list[dict]) -> dict | None:
    """Pull secret values out of the request body.

    Returns None when the body is not a valid set of fields for the provider.
    """
    names = {field["name"] for field in fields}
    body_fields = data.get("fields")
    if isinstance(body_fields, dict):
        return {key: value for key, value in body_fields.items() if key in names}
    if "key" in data:
        if names == {"key"}:
            return {"key": data["key"]}
        return None
    return {}


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

    data = request.data or {}
    fields = secret_fields(integration)
    settings_spec = config_fields(integration)

    requested = _requested_secrets(data, fields)
    if requested is None:
        return Response(
            {"detail": "'key' is not a field of this integration — send \"fields\" instead."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    cleaned: dict = {}
    for name, raw in requested.items():
        value = "" if raw is None else str(raw).strip()
        if value:
            cleaned[name] = value
    for field in fields:
        value = cleaned.get(field["name"])
        min_length = field.get("min_length", 0)
        if value is not None and len(value) < min_length:
            return Response(
                {"detail": f"{field['label']} must be at least {min_length} characters."},
                status=status.HTTP_400_BAD_REQUEST,
            )

    # Required fields may already be stored — a config-only save is fine.
    merged = {**get_credential_secrets(provider), **cleaned}
    missing = [f["label"] for f in fields if f.get("required", True) and not merged.get(f["name"])]
    if missing:
        return Response(
            {"detail": f"Missing required field(s): {', '.join(missing)}."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    config = None
    raw_config = data.get("config")
    if isinstance(raw_config, dict):
        # Config is a full replacement (the UI pre-fills it), unlike secrets,
        # which merge so settings can change without re-pasting a key.
        allowed = {field["name"] for field in settings_spec}
        config = {key: value for key, value in raw_config.items() if key in allowed}
        resolved = {key: str(value).strip() for key, value in config.items() if value not in (None, "")}
        for field in settings_spec:
            env_var = field.get("env_var")
            if field["name"] not in resolved and env_var and os.environ.get(env_var):
                resolved[field["name"]] = os.environ[env_var]
        missing_settings = [
            field["label"]
            for field in settings_spec
            if field.get("required", False) and not resolved.get(field["name"])
        ]
        if missing_settings:
            return Response(
                {"detail": f"Missing required setting(s): {', '.join(missing_settings)}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

    try:
        set_credential(provider, values=cleaned or None, config=config, user=request.user)
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(_payload(integration))
