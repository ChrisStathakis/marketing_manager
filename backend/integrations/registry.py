"""Declarative registry of third-party API keys the backend can use.

Single source of truth for the credential API, the in-app documentation and
the preview/status shown in Settings. Never put secret *values* here — only
metadata.

Each entry describes how to collect and store its settings:

``fields``
    Secret inputs. ``name`` is the storage key, ``min_length`` is validated by
    the API, ``multiline`` renders a textarea (whole JSON key files), and
    ``hint_key`` derives the display hint from that key inside a JSON value.
    A single field stores its value as a plain string; several store an
    encrypted JSON object.
``config_fields``
    Non-secret inputs (GA4 property id, Ads customer id, …) kept in the
    ``config`` JSON column and returned by the status API so the UI can
    pre-fill them. Each may declare its own ``env_var`` fallback.
``sync_endpoint``
    Optional: the API route that pulls data for this integration, surfaced as
    a “Sync now” action in Settings.

To add an integration: add one entry below (``id`` must be a lowercase slug),
then read it with ``integrations.services.get_credential_value("<id>")`` /
``get_credential_secrets("<id>")`` wherever the credentials are needed.
"""

INTEGRATIONS = [
    {
        "id": "openai",
        "label": "OpenAI",
        "summary": "AI-powered campaign suggestions",
        "description": (
            "Powers “Generate AI” on a campaign. The backend sends a metrics snapshot "
            "to OpenAI and stores the returned suggestions. Rule-based suggestions work "
            "without a key, so this is optional."
        ),
        "env_var": "OPENAI_API_KEY",
        "used_by": ["POST /api/suggestions/generate-ai/"],
        "where_to_get": "https://platform.openai.com/api-keys",
        "fields": [
            {
                "name": "key",
                "label": "API key",
                "secret": True,
                "min_length": 16,
                "placeholder": "sk-…",
                "prefix": "sk-",
                "hint": "Starts with “sk-”, minimum 16 characters. Sent once — never displayed again.",
            },
        ],
        "steps": [
            "Sign in at platform.openai.com and open “API keys”.",
            "Create a new secret key (it starts with “sk-”) and copy it once — it is only shown then.",
            "Paste it here, or set OPENAI_API_KEY in backend/.env and restart Django.",
            "Set a low usage limit on the key — suggestions only make small requests.",
        ],
        "security_note": (
            "Stored server-side only, encrypted at rest; the value is never returned by "
            "the API or included in the frontend bundle. Rotating DJANGO_SECRET_KEY makes "
            "saved keys unreadable — re-enter them after a rotation."
        ),
    },
    {
        "id": "google-analytics",
        "label": "Google Analytics 4",
        "summary": "Daily revenue and orders per campaign",
        "description": (
            "Lets the backend pull daily revenue and orders from the GA4 Data API and store "
            "them as daily metrics, so results no longer have to be imported as CSV. Report "
            "rows are matched to campaigns on utm_campaign; rows that match nothing are "
            "reported back instead of being dropped silently. GA4 has no ad cost, so spend "
            "and ROAS are left untouched."
        ),
        "env_var": "GOOGLE_ANALYTICS_CREDENTIALS",
        "used_by": ["POST /api/integrations/google-analytics/sync/"],
        "where_to_get": "https://console.cloud.google.com/iam-admin/serviceaccounts",
        "sync_endpoint": "/integrations/google-analytics/sync/",
        "fields": [
            {
                "name": "credentials_json",
                "label": "Service account JSON",
                "secret": True,
                "multiline": True,
                "min_length": 32,
                "placeholder": '{"type": "service_account", "project_id": "…"}',
                "hint_key": "client_email",
                "hint": (
                    "Paste the whole service-account key file (JSON). It is stored encrypted "
                    "and never shown again."
                ),
            },
        ],
        "config_fields": [
            {
                "name": "property_id",
                "label": "GA4 property ID",
                "env_var": "GOOGLE_ANALYTICS_PROPERTY_ID",
                "placeholder": "123456789",
                "required": True,
                "hint": "GA4 → Admin → Property settings → Property ID (digits only).",
            },
        ],
        "steps": [
            "In Google Cloud, create a project (or reuse one) and enable the “Google Analytics Data API”.",
            "Create a service account, then add a JSON key and download it.",
            "In GA4 → Admin → Property access management, add the service-account email as Viewer.",
            "Paste the JSON key file and the GA4 property ID here, then use “Sync now”.",
        ],
        "security_note": (
            "The key file is stored server-side only, encrypted at rest, and never returned by "
            "the API. The service account only needs Viewer access to this one GA4 property; "
            "rotating DJANGO_SECRET_KEY makes the stored key unreadable — re-enter it after a "
            "rotation."
        ),
    },
]

INTEGRATIONS_BY_ID = {item["id"]: item for item in INTEGRATIONS}

# A single secret field named "key" is the classic API-key shape; anything else
# is stored as an encrypted JSON object.
DEFAULT_FIELDS = [{"name": "key", "label": "API key", "secret": True, "min_length": 16}]


def get_integration(provider: str) -> dict | None:
    """Return the registry entry for a provider slug, or None if unknown."""
    return INTEGRATIONS_BY_ID.get(provider)


def secret_fields(integration: dict) -> list[dict]:
    """Secret input specs for an entry (with a sane fallback)."""
    fields = integration.get("fields") or DEFAULT_FIELDS
    return [field for field in fields if field.get("secret", True)]


def config_fields(integration: dict) -> list[dict]:
    """Non-secret input specs for an entry."""
    return integration.get("config_fields") or []
