from django.conf import settings
from django.db import models


class IntegrationCredential(models.Model):
    """A third-party API key stored by the operator, encrypted at rest.

    The plaintext value is only ever written here (via the write-only API) and
    read server-side when calling the integration — it is never serialized
    back to clients.
    """

    provider = models.SlugField(max_length=50, unique=True)
    key_encrypted = models.TextField()
    key_hint = models.CharField(max_length=8, blank=True)
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
