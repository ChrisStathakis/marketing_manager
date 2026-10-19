"""Store Instagram comments as rows. Idempotent, and offline-testable.

``resolve_post`` is pure: it turns a URL into a tracked post with no network.
``sync_post`` fetches comments through a client and upserts them, so a re-run
refreshes text and likes without creating duplicates.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone as dt_timezone

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from integrations.services import get_credential_config, get_credential_secrets

from .instagram import (
    InstagramClient,
    InstagramNotConfigured,
    media_pk_from_shortcode,
    shortcode_from_url,
)
from .models import InstagramComment, InstagramTrackedPost

PROVIDER = "instagram"
DEFAULT_MAX_COMMENTS = 500


@dataclass
class CommentSyncResult:
    """Outcome of one scrape, shaped for the API response."""

    fetched: int = 0
    created: int = 0
    updated: int = 0
    total_seen: int | None = None

    def as_dict(self) -> dict:
        return {
            "fetched": self.fetched,
            "created": self.created,
            "updated": self.updated,
            "total_seen": self.total_seen,
        }

    def summary(self) -> str:
        return f"{self.fetched} comments ({self.created} new, {self.updated} updated)"


def get_client() -> InstagramClient:
    """Build a client from the stored/env ``sessionid``. Raises when unset."""
    secrets = get_credential_secrets(PROVIDER)
    sessionid = (secrets.get("sessionid") or "").strip()
    if not sessionid:
        raise InstagramNotConfigured(
            "Instagram is not configured — paste the sessionid cookie in "
            "Settings → API keys (or set INSTAGRAM_SESSIONID)."
        )
    config = get_credential_config(PROVIDER)
    return InstagramClient(
        sessionid,
        base_url=getattr(settings, "INSTAGRAM_API_BASE", "https://www.instagram.com"),
        timeout=getattr(settings, "INSTAGRAM_TIMEOUT", 20),
        proxy=config.get("proxy") or getattr(settings, "INSTAGRAM_PROXY", None) or None,
        username=config.get("username") or "",
    )


def resolve_post(url: str) -> tuple[InstagramTrackedPost, bool]:
    """Return ``(post, created)`` for a URL, creating the row if it is new."""
    shortcode = shortcode_from_url(url)
    media_pk = media_pk_from_shortcode(shortcode)
    post, created = InstagramTrackedPost.objects.get_or_create(
        shortcode=shortcode,
        defaults={"url": url.strip(), "media_pk": media_pk},
    )
    return post, created


def _as_datetime(epoch) -> datetime | None:
    if not epoch:
        return None
    try:
        return datetime.fromtimestamp(int(epoch), tz=dt_timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


def sync_post(
    post: InstagramTrackedPost,
    *,
    amount: int | None = None,
    client: InstagramClient | None = None,
) -> CommentSyncResult:
    """Fetch this post's comments and upsert them.

    Raises the ``InstagramError`` subclasses from ``instagram`` so the view can
    map them to the right HTTP status.
    """
    client = client or get_client()
    limit = amount or getattr(settings, "INSTAGRAM_MAX_COMMENTS", DEFAULT_MAX_COMMENTS)
    comments = client.comments(post.media_pk, amount=limit)
    reported = client.comment_count(post.media_pk)

    result = CommentSyncResult(fetched=len(comments), total_seen=reported)
    with transaction.atomic():
        for comment in comments:
            if not comment.pk:
                continue  # can't deduplicate without an id
            _, created = InstagramComment.objects.update_or_create(
                post=post,
                comment_pk=comment.pk,
                defaults={
                    "author_username": comment.author_username,
                    "author_pk": comment.author_pk,
                    "author_full_name": comment.author_full_name,
                    "text": comment.text,
                    "commented_at": _as_datetime(comment.created_at_utc),
                    "like_count": comment.like_count,
                    "child_count": comment.child_count,
                },
            )
            if created:
                result.created += 1
            else:
                result.updated += 1

    post.status = "ok"
    post.error = ""
    post.last_scraped_at = timezone.now()
    # Prefer Instagram's own total; fall back to what we have actually stored.
    post.comment_count = reported if reported is not None else max(post.comment_count, result.fetched)
    post.save(update_fields=["status", "error", "last_scraped_at", "comment_count"])
    return result


def mark_failed(post: InstagramTrackedPost, error) -> None:
    """Record a failed scrape on the post without touching its comments."""
    post.status = "error"
    post.error = str(error)[:2000]
    post.save(update_fields=["status", "error"])
