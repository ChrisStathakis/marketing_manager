"""Map GA4 traffic sources onto the platforms the studio publishes to.

GA4 reports what the analytics tag saw, not what we intended: a tracked link
shows up as ``x`` with medium ``social``, an untracked Reddit link as
``reddit.com`` with medium ``referral``, and an app view as ``l.instagram.com``.
This module is the single translation table, so the report can line up "what we
posted" with "what arrived" without guessing in three places.
"""

from __future__ import annotations

#: Host or campaign source → the platform key used everywhere else in the app.
SOURCE_PLATFORMS: dict[str, str] = {
    "x": "x",
    "x.com": "x",
    "twitter": "x",
    "twitter.com": "x",
    "t.co": "x",
    "reddit": "reddit",
    "reddit.com": "reddit",
    "old.reddit.com": "reddit",
    "instagram": "instagram",
    "instagram.com": "instagram",
    "l.instagram.com": "instagram",
    "ig": "instagram",
    "tiktok": "tiktok",
    "tiktok.com": "tiktok",
    "youtube": "youtube",
    "youtube.com": "youtube",
    "youtu.be": "youtube",
    "m.youtube.com": "youtube",
    "telegram": "telegram",
    "telegram.org": "telegram",
    "t.me": "telegram",
    "discord": "discord",
    "discord.com": "discord",
    "discord.gg": "discord",
}

#: Mediums that mean "a person followed a post", as opposed to a search hit.
SOCIAL_MEDIUMS = frozenset({"social", "social-network", "social-media", "referral", "organic-social"})

_PREFIXES = ("www.", "m.", "l.", "old.", "amp.")


def normalise_source(source: str | None) -> str:
    """Lowercase a GA4 source and drop the noise prefixes."""
    value = (source or "").strip().lower()
    # GA4 sometimes reports the full referrer, sometimes just the host.
    for prefix in _PREFIXES:
        if value.startswith(prefix):
            value = value[len(prefix) :]
            break
    return value


def platform_for_source(source: str | None) -> str | None:
    """The studio platform behind a GA4 source, or ``None`` for the open web."""
    value = normalise_source(source)
    if not value:
        return None
    if value in SOURCE_PLATFORMS:
        return SOURCE_PLATFORMS[value]
    # "x.com/referral" and similar arrive as a path; compare the first segment.
    head = value.split("/", 1)[0]
    return SOURCE_PLATFORMS.get(head)


def is_social(medium: str | None) -> bool:
    return (medium or "").strip().lower() in SOCIAL_MEDIUMS
