"""Read comments from public Instagram posts with a logged-in session cookie.

Instagram retired *anonymous* access to profile/post JSON in 2026 (``web_profile_info``
answers ``429``/``401 require_login``), so this module never touches those endpoints.
Instead it converts a post URL's shortcode to a media id **locally** and calls the
authenticated comments endpoint with a ``sessionid`` cookie the operator supplies.

This is not official API usage. See ``docs/api-keys.md`` and
``docs/guide/growth.md`` for the terms-of-service and privacy caveats; keep the
feature behind ``INSTAGRAM_SCRAPER_ENABLED``.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass

try:  # curl_cffi makes the request look like a browser; declared in requirements.txt.
    from curl_cffi import requests as _creq
except ImportError:  # pragma: no cover - declared in requirements.txt
    _creq = None

#: The base64-ish alphabet Instagram uses in post shortcodes.
SHORTCODE_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"

#: The web app id Instagram's own frontend sends; required by the private API.
WEB_APP_ID = "936619743392459"

#: Post URLs look like /p/<shortcode>/, /reel/<shortcode>/ or /tv/<shortcode>/.
_SHORTCODE_RE = re.compile(r"/(?:p|reel|reels|tv)/([A-Za-z0-9_-]+)")


class InstagramError(RuntimeError):
    """Any failure talking to Instagram."""


class InstagramNotConfigured(InstagramError):
    """No ``sessionid`` credential is stored or available from the environment."""


class InstagramSessionInvalid(InstagramError):
    """Instagram rejected the stored sessionid (wrong, expired or logged out)."""


class InstagramRateLimited(InstagramError):
    """Instagram is throttling this session (HTTP 429)."""


def media_pk_from_shortcode(shortcode: str) -> int:
    """Convert a post shortcode (e.g. ``DWr6G6QkpiS``) to its numeric media id.

    The mapping is a base-64 decode over ``SHORTCODE_ALPHABET`` and needs no network.
    """
    value = 0
    for char in shortcode:
        index = SHORTCODE_ALPHABET.find(char)
        if index < 0:
            raise ValueError(f"Not a valid Instagram shortcode: {shortcode!r}")
        value = value * 64 + index
    return value


def shortcode_from_url(url: str) -> str:
    """Pull the shortcode out of a post / reel / tv URL."""
    match = _SHORTCODE_RE.search(url or "")
    if not match:
        raise ValueError(
            "Not an Instagram post URL — expected something like "
            "https://www.instagram.com/p/<shortcode>/ or …/reel/<shortcode>/."
        )
    return match.group(1)


@dataclass
class FetchedComment:
    """One comment, shaped for storage (no Instagram objects leak out)."""

    pk: str
    author_username: str
    author_pk: str = ""
    author_full_name: str = ""
    text: str = ""
    created_at_utc: int | None = None
    like_count: int = 0
    child_count: int = 0


def _comment_from_item(item: dict) -> FetchedComment:
    user = item.get("user") or {}
    return FetchedComment(
        pk=str(item.get("pk") or ""),
        author_username=str(user.get("username") or item.get("username") or ""),
        author_pk=str(user.get("pk") or user.get("id") or ""),
        author_full_name=str(user.get("full_name") or ""),
        text=str(item.get("text") or ""),
        created_at_utc=item.get("created_at") or item.get("created_at_utc"),
        like_count=int(item.get("comment_like_count") or 0),
        child_count=int(item.get("child_comment_count") or 0),
    )


class InstagramClient:
    """Thin, sessionid-authenticated client for the endpoints we actually need."""

    def __init__(
        self,
        sessionid: str,
        *,
        base_url: str = "https://www.instagram.com",
        app_id: str = WEB_APP_ID,
        timeout: int = 20,
        impersonate: str = "chrome",
        proxy: str | None = None,
        delay: float = 1.5,
        username: str = "",
    ):
        if _creq is None:
            raise InstagramError(
                "curl_cffi is not installed — run pip install -r backend/requirements.txt."
            )
        self.sessionid = (sessionid or "").strip()
        if not self.sessionid:
            raise InstagramNotConfigured("No Instagram sessionid configured.")
        self.base_url = base_url.rstrip("/")
        self.app_id = app_id
        self.timeout = timeout
        self.impersonate = impersonate
        self.proxy = proxy
        self.delay = delay
        self.username = (username or "").strip()

    def _session(self):
        session = _creq.Session()
        session.cookies.set("sessionid", self.sessionid, domain=".instagram.com")
        return session

    def _headers(self) -> dict:
        return {
            "x-ig-app-id": self.app_id,
            "x-asbd-id": "129477",
            "x-ig-www-claim": "0",
            "x-requested-with": "XMLHttpRequest",
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Origin": self.base_url,
            "Referer": f"{self.base_url}/",
        }

    def _get(self, path: str, *, params: dict | None = None):
        session = self._session()
        kwargs = {"headers": self._headers(), "timeout": self.timeout, "impersonate": self.impersonate}
        if self.proxy:
            kwargs["proxies"] = {"http": self.proxy, "https": self.proxy}
        response = session.get(f"{self.base_url}{path}", params=params or {}, **kwargs)
        if response.status_code in (401, 403):
            raise InstagramSessionInvalid(
                "Instagram rejected the sessionid — it is wrong, expired or logged out. "
                "Log in again in a browser and copy a fresh sessionid cookie."
            )
        if response.status_code == 429:
            raise InstagramRateLimited(
                "Instagram is rate-limiting this session (HTTP 429). Wait a few minutes and retry."
            )
        return response

    def validate(self) -> str:
        """Return the logged-in username, or raise if the session is not usable.

        ``accounts/current_user`` names the account the cookie belongs to, but it is
        undocumented and occasionally unavailable, so a plain profile read is used as a
        fallback (it proves the cookie is accepted even when it cannot name the account).
        """
        response = self._get("/api/v1/accounts/current_user/", params={"edit": "false"})
        if response.status_code == 200:
            try:
                user = response.json().get("user") or {}
            except ValueError:
                user = {}
            username = user.get("username") or ""
            if username:
                return username

        probe = self._get("/api/v1/users/web_profile_info/", params={"username": self.username or "instagram"})
        if probe.status_code != 200:
            raise InstagramError(
                f"Instagram returned HTTP {probe.status_code} while checking the session."
            )
        try:
            user = ((probe.json().get("data") or {}).get("user") or {})
        except ValueError:
            user = {}
        return user.get("username") or self.username or "unknown"

    def comments(self, media_pk: int, *, amount: int | None = None) -> list[FetchedComment]:
        """Fetch comments for a media id, newest first, following pagination.

        Instagram's web endpoint reports ``next_max_id`` but expects it back as ``min_id``.
        A page that adds nothing new ends the loop, so a cursor mismatch degrades to the
        first page instead of spinning forever.
        """
        collected: list[FetchedComment] = []
        seen: set[str] = set()
        cursor: str | None = None
        while True:
            params = {"can_support_threading": "true", "permalink_enabled": "false"}
            if cursor:
                params["min_id"] = cursor
            response = self._get(f"/api/v1/media/{media_pk}/comments/", params=params)
            if response.status_code != 200:
                raise InstagramError(
                    f"Instagram returned HTTP {response.status_code} for the comments of media {media_pk}."
                )
            try:
                data = response.json()
            except ValueError as exc:
                raise InstagramError("Instagram returned a non-JSON comments payload.") from exc

            fresh = 0
            for item in data.get("comments") or []:
                if not isinstance(item, dict):
                    continue
                comment = _comment_from_item(item)
                if comment.pk:
                    if comment.pk in seen:
                        continue
                    seen.add(comment.pk)
                collected.append(comment)
                fresh += 1

            if amount and len(collected) >= amount:
                break
            if not data.get("has_more_comments"):
                break
            cursor = data.get("next_max_id")
            if not cursor or fresh == 0:
                break
            time.sleep(self.delay)

        return collected[:amount] if amount else collected

    def comment_count(self, media_pk: int) -> int | None:
        """Best-effort total comment count Instagram reports for a media id.

        Never raises: the value is a nice-to-have, so a throttle or a dead session here
        must not turn a successful comment fetch into a failure.
        """
        try:
            response = self._get(
                f"/api/v1/media/{media_pk}/comments/", params={"can_support_threading": "true"}
            )
        except InstagramError:
            return None
        if response.status_code != 200:
            return None
        try:
            value = response.json().get("comment_count")
        except ValueError:
            return None
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None
