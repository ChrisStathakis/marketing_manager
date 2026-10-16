"""Credential storage and lookup for third-party API keys.

Precedence when a key is needed (highest first):
1. explicit per-request override (handled by callers, e.g. suggestions);
2. stored credential in the database (encrypted at rest);
3. environment variable fallback (backend/.env).
"""
import logging
import os

from .crypto import DecryptionError, decrypt, encrypt
from .models import IntegrationCredential
from .registry import get_integration

logger = logging.getLogger(__name__)


def set_credential(provider: str, raw_key: str, user=None) -> IntegrationCredential:
    """Store (or replace) a key, encrypted, with a display hint."""
    credential, _ = IntegrationCredential.objects.update_or_create(
        provider=provider,
        defaults={
            "key_encrypted": encrypt(raw_key),
            "key_hint": raw_key[-4:],
            "updated_by": user,
        },
    )
    return credential


def delete_credential(provider: str) -> None:
    """Remove the stored key (env fallback, if set, becomes active again)."""
    IntegrationCredential.objects.filter(provider=provider).delete()


def get_credential_value(provider: str) -> str | None:
    """Effective key value: stored (decrypted) first, env fallback, else None."""
    stored = IntegrationCredential.objects.filter(provider=provider).first()
    if stored is not None:
        try:
            return decrypt(stored.key_encrypted)
        except DecryptionError:
            logger.warning(
                "Stored credential for %r cannot be decrypted (was DJANGO_SECRET_KEY rotated?); "
                "falling back to the environment variable.",
                provider,
            )
    integration = get_integration(provider)
    if integration is None:
        return None
    return os.environ.get(integration["env_var"]) or None


def credential_status(provider: str) -> dict:
    """Configuration status for the API/UI. Never includes the key value."""
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

    env_set = bool(integration and os.environ.get(integration["env_var"]))
    source = "database" if stored_ok else ("env" if env_set else None)
    return {
        "configured": source is not None,
        "source": source,
        "key_hint": stored.key_hint if stored is not None else None,
        "stored": stored is not None,
        "stored_unreadable": stored is not None and not stored_ok,
        "updated_at": stored.updated_at if stored is not None else None,
        "updated_by": stored.updated_by.username if stored and stored.updated_by else None,
    }
