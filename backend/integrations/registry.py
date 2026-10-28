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
    {
        "id": "google-search-console",
        "label": "Google Search Console",
        "summary": "Organic search clicks, impressions, pages and queries",
        "description": (
            "Pulls Google organic search performance into the growth report: clicks, "
            "impressions, CTR, average position, top pages and top queries. Search "
            "Console has no UTM/campaign dimension, so campaign reports join it through "
            "the canonical pages linked by the campaign and label the result as assisted "
            "search — use GA4 for true UTM attribution."
        ),
        "env_var": "GOOGLE_SEARCH_CONSOLE_CREDENTIALS",
        "used_by": [
            "POST /api/integrations/google-search-console/sync/",
            "GET /api/growth/search-console/",
        ],
        "where_to_get": "https://search.google.com/search-console",
        "sync_endpoint": "/integrations/google-search-console/sync/",
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
                    "Paste the whole service-account key file (JSON). The same account can "
                    "be used for GA4. It is stored encrypted and never shown again."
                ),
            },
        ],
        "config_fields": [
            {
                "name": "site_url",
                "label": "Search Console property",
                "env_var": "GOOGLE_SEARCH_CONSOLE_SITE_URL",
                "placeholder": "sc-domain:catchandstats.com",
                "required": True,
                "hint": (
                    "Use the exact property string: sc-domain:example.com for a Domain "
                    "property, or https://www.example.com/ for a URL-prefix property."
                ),
            },
        ],
        "steps": [
            "In Google Cloud, enable the “Google Search Console API” (you can reuse the GA4 project).",
            "Create a service account and download a JSON key, or reuse the GA4 service account.",
            "In Search Console → Settings → Users and permissions, add the service-account client_email as Full or Restricted user.",
            "Paste the JSON and the exact property here, then use “Sync now”.",
        ],
        "security_note": (
            "The key file is stored server-side only, encrypted at rest, and never returned by "
            "the API. The service account only needs read access to this Search Console property; "
            "rotating DJANGO_SECRET_KEY makes the stored key unreadable — re-enter it after a "
            "rotation."
        ),
    },
    {
        "id": "instagram",
        "label": "Instagram (session)",
        "summary": "Who commented on a public post — audience research",
        "description": (
            "Lets the growth studio read the commenters on a **public** Instagram post. "
            "Instagram stopped serving post data to logged-out requests in 2026, so this uses "
            "the sessionid cookie from a logged-in account (a burner is fine) to call the "
            "comments endpoint. This is not official API usage: it can break, and the account "
            "behind the cookie risks action. Likers are not available by any method."
        ),
        "env_var": "INSTAGRAM_SESSIONID",
        "used_by": [
            "POST /api/growth/instagram/posts/{id}/scrape/",
            "POST /api/growth/instagram/test/",
        ],
        "where_to_get": "https://www.instagram.com",
        "fields": [
            {
                "name": "sessionid",
                "label": "sessionid cookie",
                "secret": True,
                "min_length": 20,
                "placeholder": "12345678%3AAbCdEf…",
                "hint": (
                    "Log in to Instagram in a browser, open DevTools → Application → Cookies, "
                    "copy the value of the “sessionid” cookie for instagram.com. It is stored "
                    "encrypted and never shown again."
                ),
            },
        ],
        "config_fields": [
            {
                "name": "username",
                "label": "Account username (label only)",
                "env_var": "INSTAGRAM_USERNAME",
                "placeholder": "my_burner",
                "hint": "Only used to label the connection; the sessionid is what authenticates.",
            },
            {
                "name": "proxy",
                "label": "Proxy URL (optional)",
                "env_var": "INSTAGRAM_PROXY",
                "placeholder": "http://user:pass@host:port",
                "hint": "Route requests through a proxy to avoid rate limits on your own IP.",
            },
        ],
        "steps": [
            "Log in to Instagram in a browser (use a throwaway account if you prefer).",
            "Open DevTools → Application → Cookies → https://www.instagram.com and copy the “sessionid” value.",
            "Paste it here (or set INSTAGRAM_SESSIONID in backend/.env), then use “Test connection”.",
            "Sessions expire: if requests start failing with 401, log in again and paste a fresh cookie.",
        ],
        "security_note": (
            "The cookie is stored server-side only, encrypted at rest, and never returned by the "
            "API. It grants full access to the account it belongs to, so treat it like a "
            "password and use a burner. Experimental feature — it depends on Instagram’s private "
            "endpoints and may stop working without notice."
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
