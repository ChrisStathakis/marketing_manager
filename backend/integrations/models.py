from django.conf import settings
from django.db import models


class IntegrationCredential(models.Model):
    """A third-party API key stored by the operator, encrypted at rest.

    The plaintext value is only ever written here (via the write-only API) and
    read server-side when calling the integration — it is never serialized
    back to clients.

    ``config`` holds non-secret settings the integration needs (a GA4 property
    id, an Ads customer id, …) and *is* returned by the status API. The sync
    bookkeeping fields are also non-secret and best-effort: they are only
    written when a row exists (a key coming from ``backend/.env`` has none).
    """

    provider = models.SlugField(max_length=50, unique=True)
    key_encrypted = models.TextField()
    key_hint = models.CharField(max_length=255, blank=True)
    config = models.JSONField(default=dict, blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    last_sync_error = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    def __str__(self):
        return f"{self.provider} credential"
