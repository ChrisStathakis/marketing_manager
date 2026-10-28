"""Minimal Google Search Console API client.

Search Console reports *Google organic search* only. Its dimensions are date,
query, page, country, device and search appearance; there is deliberately no
UTM/campaign dimension, so campaign reports use the pages linked by a campaign
as the join key (see ``growth.search_console``).

Like :mod:`google_sync.ga4`, this uses a service-account JWT and ``urllib`` so
the backend does not need the Google SDK. The service account must be added as
a user of the exact Search Console property configured in Settings.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from typing import Iterable

from .ga4 import GA4Error, _access_token

SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
API_ROOT = "https://searchconsole.googleapis.com/webmasters/v3"
MAX_ROW_LIMIT = 25_000
MAX_SYNC_ROWS = 50_000
DEFAULT_TIMEOUT = 30

#: Dimensions per stored scope. Keeping these separate avoids one very wide
#: page×query table and lets the report answer "which pages" and "which
#: queries" without re-querying Google.
SCOPES_BY_SCOPE = {
    "total": ["date"],
    "page": ["date", "page"],
    "query": ["date", "query"],
}


class SearchConsoleError(RuntimeError):
    """Credentials are missing/invalid, or the Search Console API refused us."""


def _access(credentials_json: str, timeout: int = DEFAULT_TIMEOUT) -> str:
    try:
        return _access_token(
            credentials_json,
            timeout=timeout,
            scopes=SCOPES,
            label="Google Search Console",
        )
    except GA4Error as exc:
        raise SearchConsoleError(str(exc)) from exc


def _request(
    url: str,
    token: str,
    body: dict | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST" if body is not None else "GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:500]
        raise SearchConsoleError(f"Search Console API error {exc.code}: {detail}") from exc
    except OSError as exc:
        raise SearchConsoleError(f"Could not reach the Search Console API: {exc}") from exc
    except (TypeError, ValueError) as exc:
        raise SearchConsoleError(f"Search Console returned an unreadable response: {exc}") from exc


def _site_path(site_url: str) -> str:
    """URL-encode the exact property string for the API path."""
    return urllib.parse.quote(site_url, safe="")


def list_sites(credentials_json: str, timeout: int = DEFAULT_TIMEOUT) -> list[dict]:
    """Properties the service account can read (used by 'Test connection')."""
    payload = _request(f"{API_ROOT}/sites", _access(credentials_json, timeout), timeout=timeout)
    rows = payload.get("siteEntry") or []
    return [
        {
            "site_url": str(row.get("siteUrl") or ""),
            "permission_level": str(row.get("permissionLevel") or ""),
        }
        for row in rows
        if isinstance(row, dict)
    ]


def query(
    credentials_json: str,
    site_url: str,
    start_date,
    end_date,
    dimensions: Iterable[str],
    *,
    row_limit: int = MAX_ROW_LIMIT,
    start_row: int = 0,
    data_state: str = "all",
    timeout: int = DEFAULT_TIMEOUT,
) -> dict:
    """Run one Search Analytics query for an inclusive date range."""
    body = {
        "startDate": start_date.isoformat(),
        "endDate": end_date.isoformat(),
        "dimensions": list(dimensions),
        "rowLimit": max(1, min(int(row_limit), MAX_ROW_LIMIT)),
        "startRow": max(0, int(start_row)),
        "dataState": data_state,
    }
    url = f"{API_ROOT}/sites/{_site_path(site_url)}/searchAnalytics/query"
    return _request(url, _access(credentials_json, timeout), body=body, timeout=timeout)


def _fetch_rows(
    credentials_json: str,
    site_url: str,
    start_date,
    end_date,
    dimensions: list[str],
    *,
    max_rows: int = MAX_SYNC_ROWS,
    timeout: int = DEFAULT_TIMEOUT,
) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    while len(rows) < max_rows:
        limit = min(MAX_ROW_LIMIT, max_rows - len(rows))
        payload = query(
            credentials_json,
            site_url,
            start_date,
            end_date,
            dimensions,
            row_limit=limit,
            start_row=offset,
            timeout=timeout,
        )
        batch = payload.get("rows") or []
        rows.extend(batch)
        if len(batch) < limit:
            break
        offset += len(batch)
    return rows


def normalize_page_path(url: str) -> str:
    """Canonical path used to join Search Console pages to campaign links.

    Search Console reports canonical pages, not the UTM-tagged URL that was
    clicked, so query strings and www/non-www differences are intentionally
    discarded here.
    """
    parsed = urllib.parse.urlparse(str(url or ""))
    path = urllib.parse.unquote(parsed.path or "/")
    if not path.startswith("/"):
        path = f"/{path}"
    return path.rstrip("/") or "/"


def _number(value) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def parse_rows(payload: dict, scope: str) -> list[dict]:
    """Turn a Search Analytics response into storage rows for one scope."""
    rows: list[dict] = []
    for row in payload.get("rows") or []:
        if not isinstance(row, dict):
            continue
        keys = row.get("keys") or []
        if not keys:
            continue
        try:
            day = date.fromisoformat(str(keys[0])[:10])
        except (TypeError, ValueError):
            continue

        page_url = ""
        page_path = ""
        query_text = ""
        if scope == "page" and len(keys) > 1:
            page_url = str(keys[1] or "")[:2000]
            page_path = normalize_page_path(page_url)
        elif scope == "query" and len(keys) > 1:
            query_text = str(keys[1] or "")[:500]

        rows.append(
            {
                "date": day,
                "scope": scope,
                "page_url": page_url,
                "page_path": page_path,
                "query": query_text,
                "clicks": int(round(_number(row.get("clicks")))),
                "impressions": int(round(_number(row.get("impressions")))),
                "ctr": _number(row.get("ctr")),
                "position": _number(row.get("position")),
            }
        )
    return rows


def fetch_snapshot(
    credentials_json: str,
    site_url: str,
    start_date,
    end_date,
    *,
    timeout: int = DEFAULT_TIMEOUT,
) -> list[dict]:
    """Fetch site totals, page rows and query rows for one date range.

    Search Console returns at most 25k rows per request and only the top rows
    for very large properties; we paginate up to ``MAX_SYNC_ROWS`` per scope and
    leave the rest to Google's own limits.
    """
    rows: list[dict] = []
    for scope, dimensions in SCOPES_BY_SCOPE.items():
        payload_rows = _fetch_rows(
            credentials_json,
            site_url,
            start_date,
            end_date,
            dimensions,
            timeout=timeout,
        )
        rows.extend(parse_rows({"rows": payload_rows}, scope))
    return rows


__all__ = [
    "DEFAULT_TIMEOUT",
    "MAX_ROW_LIMIT",
    "SearchConsoleError",
    "fetch_snapshot",
    "list_sites",
    "normalize_page_path",
    "parse_rows",
    "query",
]
