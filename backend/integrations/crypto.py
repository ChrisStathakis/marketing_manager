"""Symmetric encryption for stored integration keys.

The Fernet key is derived from DJANGO_SECRET_KEY, so no extra secret has to be
managed — but rotating DJANGO_SECRET_KEY makes previously stored keys
unreadable (they must be re-entered; callers handle this gracefully).
"""
import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


class DecryptionError(Exception):
    """Stored token cannot be decrypted (e.g. DJANGO_SECRET_KEY was rotated)."""


def _fernet() -> Fernet:
    digest = hashlib.sha256(f"{settings.SECRET_KEY}:integration-keys".encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt(value: str) -> str:
    """Encrypt a plaintext key into a storable token."""
    return _fernet().encrypt(value.encode()).decode()


def decrypt(token: str) -> str:
    """Decrypt a stored token. Raises DecryptionError if the token is invalid."""
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise DecryptionError("Stored key cannot be decrypted.") from exc
