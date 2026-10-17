"""Credential storage and lookup for third-party API keys.

Precedence when a key is needed (highest first):
1. explicit per-request override (handled by callers, e.g. suggestions);
2. stored credential in the database (encrypted at rest);
3. environment variable fallback (backend/.env).

An integration may declare several *secret* fields (stored as one encrypted
JSON blob) plus non-secret ``config_fields`` (stored as plain JSON and safe to
return to clients — property ids, customer ids, …).
"""
import json
import logging
import os

from django.utils import timezone

from .crypto import DecryptionError, decrypt, encrypt
from .models import IntegrationCredential
from .registry import config_fields, get_integration, secret_fields

logger = logging.getLogger(__name__)

HINT_MAX_LENGTH = 255


def _unpack_secrets(names: list[str], raw: str) -> dict:
    """Turn a stored/env payload into ``{field_name: value}``."""
    if len(names) == 1:
        return {names[0]: raw}
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {name: str(data[name]) for name in names if data.get(name)}


def _pack_secrets(fields: list[dict], values: dict) -> str:
    """Serialise secret values: plain string for one field, JSON for several."""
    names = [field["name"] for field in fields]
    data = {name: str(values[name]).strip() for name in names if values.get(name)}
    if len(names) == 1:
        return data.get(names[0], "")
    return json.dumps(data)


def _derive_hint(fields: list[dict], values: dict) -> str:
    """Display hint: a named key inside a JSON value, else the last 4 chars."""
    if not fields:
        return ""
    field = fields[0]
    raw = values.get(field["name"]) or ""
    hint_key = field.get("hint_key")
    if hint_key:
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            data = None
        if isinstance(data, dict) and data.get(hint_key):
            return str(data[hint_key])[:HINT_MAX_LENGTH]
    return raw[-4:]


def set_credential(provider: str, values: dict | None = None, config: dict | None = None, user=None) -> IntegrationCredential:
    """Store (or replace) an integration's secrets and/or non-secret config.

    ``values`` maps secret field name → plaintext; keys that are absent keep
    their stored value. Passing neither ``values`` nor an existing row raises
    ``ValueError``.
    """
    integration = get_integration(provider)
    if integration is None:
        raise ValueError(f"Unknown integration: {provider!r}")

    fields = secret_fields(integration)
    defaults: dict = {"updated_by": user}

    if values:
        merged = get_credential_secrets(provider)
        merged.update({key: value for key, value in values.items() if value not in (None, "")})
        defaults["key_encrypted"] = encrypt(_pack_secrets(fields, merged))
        defaults["key_hint"] = _derive_hint(fields, merged)
    elif not IntegrationCredential.objects.filter(provider=provider).exists():
        raise ValueError("Provide the credential fields before saving settings.")

    if config is not None:
        defaults["config"] = {
            key: str(value).strip() for key, value in config.items() if value not in (None, "")
        }

    credential, _ = IntegrationCredential.objects.update_or_create(
        provider=provider, defaults=defaults
    )
    return credential


def delete_credential(provider: str) -> None:
    """Remove the stored key (env fallback, if set, becomes active again)."""
    IntegrationCredential.objects.filter(provider=provider).delete()


def get_credential_secrets(provider: str) -> dict:
    """Effective secrets as ``{field_name: value}`` (stored first, then env)."""
    integration = get_integration(provider)
    if integration is None:
        return {}
    names = [field["name"] for field in secret_fields(integration)]

    stored = IntegrationCredential.objects.filter(provider=provider).first()
    if stored is not None:
        try:
            return _unpack_secrets(names, decrypt(stored.key_encrypted))
        except DecryptionError:
            logger.warning(
                "Stored credential for %r cannot be decrypted (was DJANGO_SECRET_KEY rotated?); "
                "falling back to the environment variable.",
                provider,
            )

    env_value = os.environ.get(integration["env_var"]) or None
    return _unpack_secrets(names, env_value) if env_value else {}


def get_credential_value(provider: str) -> str | None:
    """The single secret of a one-field integration (e.g. the OpenAI key)."""
    integration = get_integration(provider)
    if integration is None:
        return None
    fields = secret_fields(integration)
    if len(fields) != 1:
        return None
    return get_credential_secrets(provider).get(fields[0]["name"])


def get_credential_config(provider: str) -> dict:
    """Effective non-secret config, per-field env fallback included."""
    integration = get_integration(provider)
    if integration is None:
        return {}
    stored = IntegrationCredential.objects.filter(provider=provider).first()
    stored_config = stored.config if stored is not None and isinstance(stored.config, dict) else {}

    resolved: dict = {}
    for field in config_fields(integration):
        value = stored_config.get(field["name"])
        if value in (None, ""):
            env_var = field.get("env_var")
            if env_var:
                value = os.environ.get(env_var)
        if value not in (None, ""):
            resolved[field["name"]] = str(value)
    return resolved


def credential_status(provider: str) -> dict:
    """Configuration status for the API/UI. Never includes a secret value."""
    integration = get_integration(provider)
    stored = (
        IntegrationCredential.objects.filter(provider=provider)
        .select_related("updated_by")
        .first()
    )

    stored_ok = False
    if stored is not None:
        try:
            decrypt(stored.key_encrypted)
            stored_ok = True
        except DecryptionError:
            stored_ok = False

    secrets = get_credential_secrets(provider) if stored is None or stored_ok else {}
    secrets_ok = bool(secrets) and all(secrets.get(f["name"]) for f in secret_fields(integration or {}))

    config = get_credential_config(provider)
    config_ok = all(
        config.get(field["name"])
        for field in config_fields(integration or {})
        if field.get("required", False)
    )

    env_set = bool(integration and os.environ.get(integration["env_var"]))
    source = "database" if stored_ok else ("env" if env_set else None)
    return {
        "configured": secrets_ok and config_ok,
        "source": source,
        "key_hint": stored.key_hint if stored is not None else None,
        "stored": stored is not None,
        "stored_unreadable": stored is not None and not stored_ok,
        "config": config,
        "last_synced_at": stored.last_synced_at if stored is not None else None,
        "last_sync_error": stored.last_sync_error if stored is not None else "",
        "updated_at": stored.updated_at if stored is not None else None,
        "updated_by": stored.updated_by.username if stored and stored.updated_by else None,
    }


def record_sync(provider: str, error: str | None = None) -> int:
    """Best-effort sync bookkeeping; no-op when the key comes from the env.

    A failure only records the message, so ``last_synced_at`` keeps pointing at
    the last *successful* run.
    """
    updates: dict = {"last_sync_error": error or ""}
    if error is None:
        updates["last_synced_at"] = timezone.now()
    return IntegrationCredential.objects.filter(provider=provider).update(**updates)
