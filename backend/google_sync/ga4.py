"""Minimal GA4 Data API client.

Talking to Google means two HTTP calls: the service-account JWT is exchanged for
an access token, then that token is used against the GA4 Data API. Both go out
with ``urllib`` and the JWT is signed with ``cryptography`` (already a
dependency for credential encryption) — so neither a google-auth transport nor
the heavy google-analytics-data SDK is required, and failures surface with the
actual HTTP status.

Docs:
- https://developers.google.com/identity/protocols/oauth2/service-account
- https://developers.google.com/analytics/devguides/reporting/data/v1
"""
import base64
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from decimal import Decimal, InvalidOperation

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

SCOPES = ["https://www.googleapis.com/auth/analytics.readonly"]
DEFAULT_TOKEN_URI = "https://oauth2.googleapis.com/token"
API_ROOT = "https://analyticsdata.googleapis.com/v1beta"
JWT_LIFETIME_SECONDS = 3600

# GA4 returns dates as "YYYYMMDD".
_DATE_FORMAT = "%Y%m%d"

# Dimensions/metrics the sync relies on. sessionCampaignName is the utm_campaign
# of the session, which is how campaigns are identified throughout the app.
DIMENSIONS = ["date", "sessionCampaignName"]
METRICS = ["totalRevenue", "transactions"]


class GA4Error(RuntimeError):
    """Credentials are missing/invalid, or the GA4 API refused the request."""


def _b64(raw: bytes) -> str:
    """URL-safe base64 without padding, as JWT requires."""
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _load_credentials(credentials_json: str) -> dict:
    try:
        info = json.loads(credentials_json)
    except (TypeError, ValueError) as exc:
        raise GA4Error(
            "Google Analytics credentials are not valid JSON — paste the whole "
            "service-account key file."
        ) from exc
    if not isinstance(info, dict) or not info.get("client_email") or not info.get("private_key"):
        raise GA4Error(
            "Google Analytics credentials look incomplete — expected a service-account "
            "key file with client_email and private_key."
        )
    return info


def signed_jwt(info: dict, token_uri: str, now: int | None = None) -> str:
    """Build the RS256 JWT assertion that is exchanged for an access token."""
    issued_at = int(now if now is not None else time.time())
    header: dict = {"alg": "RS256", "typ": "JWT"}
    if info.get("private_key_id"):
        header["kid"] = info["private_key_id"]
    claims = {
        "iss": info["client_email"],
        "scope": " ".join(SCOPES),
        "aud": token_uri,
        "iat": issued_at,
        "exp": issued_at + JWT_LIFETIME_SECONDS,
    }
    try:
        private_key = serialization.load_pem_private_key(str(info["private_key"]).encode(), password=None)
    except Exception as exc:
        raise GA4Error("The private_key in the service-account JSON is not a valid PEM key.") from exc

    segments = [
        _b64(json.dumps(part, separators=(",", ":")).encode())
        for part in (header, claims)
    ]
    signing_input = ".".join(segments).encode()
    signature = private_key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    return f"{signing_input.decode()}.{_b64(signature)}"


def _access_token(credentials_json: str, timeout: int = 30) -> str:
    info = _load_credentials(credentials_json)
    token_uri = info.get("token_uri") or DEFAULT_TOKEN_URI
    body = urllib.parse.urlencode(
        {
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": signed_jwt(info, token_uri),
        }
    ).encode()
    request = urllib.request.Request(
        token_uri,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:300]
        raise GA4Error(
            f"Google rejected the service-account credentials ({exc.code}): {detail}"
        ) from exc
    except OSError as exc:  # URLError, timeouts, DNS, ...
        raise GA4Error(f"Could not reach Google's token endpoint: {exc}") from exc
    except (TypeError, ValueError) as exc:
        raise GA4Error(f"Google returned an unreadable token response: {exc}") from exc

    token = payload.get("access_token") if isinstance(payload, dict) else None
    if not token:
        raise GA4Error(f"Google did not return an access token: {str(payload)[:300]}")
    return token


def _to_decimal(value) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


def _to_int(value) -> int:
    try:
        return int(Decimal(str(value)))
    except (InvalidOperation, TypeError, ValueError):
        return 0


def _parse_date(value) -> str | None:
    try:
        return datetime.strptime(str(value), _DATE_FORMAT).date().isoformat()
    except (TypeError, ValueError):
        return None


def parse_report(payload: dict) -> list[dict]:
    """Turn a GA4 ``runReport`` response into report rows.

    Returns ``[{"date": "YYYY-MM-DD", "campaign": str, "revenue": Decimal,
    "orders": int}]``; rows with an unparseable date are skipped.
    """
    rows = []
    for row in payload.get("rows") or []:
        dimensions = [value.get("value", "") for value in row.get("dimensionValues") or []]
        metrics = [value.get("value", "0") for value in row.get("metricValues") or []]
        if len(dimensions) < len(DIMENSIONS) or len(metrics) < len(METRICS):
            continue
        day = _parse_date(dimensions[0])
        if day is None:
            continue
        rows.append(
            {
                "date": day,
                "campaign": dimensions[1],
                "revenue": _to_decimal(metrics[0]),
                "orders": _to_int(metrics[1]),
            }
        )
    return rows


def fetch_campaign_daily(
    credentials_json: str,
    property_id: str,
    start_date,
    end_date,
    timeout: int = 30,
) -> list[dict]:
    """Fetch per-day, per-campaign revenue and orders for an inclusive range."""
    token = _access_token(credentials_json, timeout=timeout)
    body = json.dumps(
        {
            "dateRanges": [
                {"startDate": start_date.isoformat(), "endDate": end_date.isoformat()}
            ],
            "dimensions": [{"name": name} for name in DIMENSIONS],
            "metrics": [{"name": name} for name in METRICS],
            "limit": 100000,
        }
    ).encode()
    request = urllib.request.Request(
        f"{API_ROOT}/properties/{property_id}:runReport",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:500]
        raise GA4Error(f"GA4 API error {exc.code}: {detail}") from exc
    except OSError as exc:
        raise GA4Error(f"Could not reach the GA4 API: {exc}") from exc
    except (TypeError, ValueError) as exc:
        raise GA4Error(f"GA4 returned an unreadable response: {exc}") from exc
    return parse_report(payload)
