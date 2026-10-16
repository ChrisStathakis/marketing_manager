"""Declarative registry of third-party API keys the backend can use.

Single source of truth for the credential API, the in-app documentation and
the preview/status shown in Settings. Never put secret *values* here — only
metadata.

To add an integration: add one entry below (``id`` must be a lowercase slug),
then call ``integrations.services.get_credential_value("<id>")`` wherever the
key is needed.
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
]

INTEGRATIONS_BY_ID = {item["id"]: item for item in INTEGRATIONS}


def get_integration(provider: str) -> dict | None:
    """Return the registry entry for a provider slug, or None if unknown."""
    return INTEGRATIONS_BY_ID.get(provider)
