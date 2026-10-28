"""Caption drafts in the languages the site actually speaks, plus local hooks.

The site's UI is English + Greek, so those two get full drafts. Turkish,
Serbian and Lithuanian get a native hook and call-to-action around an English
body: enough to not feel like a foreign post, cheap enough to keep one person
publishing four markets in under four hours a week.

Nothing here posts anywhere. It fills the clipboard; a human presses send.
"""

from __future__ import annotations

from .metrics import metric_label

PLATFORMS = ("x", "instagram", "reddit", "tiktok", "facebook", "youtube", "linkedin", "telegram")
LOCALES = ("en", "el", "tr", "sr", "lt")

#: Character budgets that actually matter (X hard limit, the rest soft).
LIMITS = {
    "x": 280,
    "instagram": 2200,
    "reddit": 40000,
    "tiktok": 2200,
    "facebook": 63206,
    "youtube": 5000,
    "linkedin": 3000,
    "telegram": 4096,
}

#: Full translations. The rest are "hook + English body" by design.
FULL_LOCALES = {"en", "el"}

HOOKS: dict[str, dict[str, str]] = {
    "player": {
        "en": "The numbers behind the headline: {subject}",
        "el": "Τα νούμερα πίσω από τον τίτλο: {subject}",
        "tr": "Manşetin arkasındaki sayılar: {subject}",
        "sr": "Brojke iza naslova: {subject}",
        "lt": "Skaičiai už antraštės: {subject}",
    },
    "metric": {
        "en": "One number that explains more than the box score: {subject}",
        "el": "Ένα νούμερο που εξηγεί περισσότερα από το box score: {subject}",
        "tr": "Box score'dan fazlasını anlatan tek bir sayı: {subject}",
        "sr": "Jedan broj koji objašnjava više od box score-a: {subject}",
        "lt": "Vienas skaičius, pasakantis daugiau nei statistika: {subject}",
    },
    "comparison": {
        "en": "Same floor, different games. {subject}",
        "el": "Ίδιο παρκέ, διαφορετικό παιχνίδι. {subject}",
        "tr": "Aynı parke, farklı oyun. {subject}",
        "sr": "Isti teren, drugačija igra. {subject}",
        "lt": "Ta pati aikštė, kitas žaidimas. {subject}",
    },
    "round_recap": {
        "en": "Five numbers from this round you will not see on a highlight reel",
        "el": "Πέντε νούμερα από αυτή τη στροφή που δεν θα δεις σε highlight reel",
        "tr": "Bu haftanın highlight'larında göremeyeceğin beş sayı",
        "sr": "Pet brojeva iz ovog kola koje nećeš videti u highlight-u",
        "lt": "Penki šio turo skaičiai, kurių nerasite highlight'uose",
    },
    "matchup": {
        "en": "What actually decides this game: {subject}",
        "el": "Τι κρίνει πραγματικά αυτό το παιχνίδι: {subject}",
        "tr": "Bu maçı gerçekte ne belirliyor: {subject}",
        "sr": "Šta zapravo odlučuje ovaj duel: {subject}",
        "lt": "Kas iš tikrųjų nulems šias rungtynes: {subject}",
    },
    "team": {
        "en": "The four factors behind {subject}, with last season next to them",
        "el": "Τα τέσσερα factors πίσω από {subject}, δίπλα στα περσινά",
        "tr": "{subject} arkasındaki dört faktör, geçen sezonla birlikte",
        "sr": "Četiri faktora iza {subject}, uz prošlu sezonu",
        "lt": "Keturi {subject} faktoriai, šalia praėjusio sezono",
    },
    "team_delta": {
        "en": "What changed for {subject} since last season",
        "el": "Τι άλλαξε για {subject} από πέρσι",
        "tr": "{subject} için geçen sezondan bu yana ne değişti",
        "sr": "Šta se promenilo za {subject} od prošle sezone",
        "lt": "Kas pasikeitė {subject} nuo praėjusio sezono",
    },
    "top8": {
        "en": "The Top 8, sorted by record and then net rating",
        "el": "Το Top 8, με ρεκόρ και μετά καθαρή αξιολόγηση",
        "tr": "İlk 8: önce galibiyet, sonra net rating",
        "sr": "Top 8: prvo skor, zatim net rejting",
        "lt": "Top 8: pirmiausia rezultatas, tada net reitingas",
    },
}

CTAS = {
    "en": "Full profile and metric definitions → {link}",
    "el": "Πλήρες προφίλ και ορισμοί μετρικών → {link}",
    "tr": "Tam profil ve metrik tanımları → {link}",
    "sr": "Ceo profil i definicije metrika → {link}",
    "lt": "Visas profilis ir metrikų aprašymai → {link}",
}

CTA_NO_LINK = {
    "en": "Full data: catchandstats.com",
    "el": "Πλήρη δεδομένα: catchandstats.com",
    "tr": "Tüm veriler: catchandstats.com",
    "sr": "Svi podaci: catchandstats.com",
    "lt": "Visi duomenys: catchandstats.com",
}

HASHTAGS = {
    "en": ("#EuroLeague", "#EuroLeagueStats", "#BasketballAnalytics"),
    "el": ("#EuroLeague", "#Ευρωλίγκα", "#Μπάσκετ"),
    "tr": ("#EuroLeague", "#Basketbol", "#İstatistik"),
    "sr": ("#EuroLeague", "#Košarka", "#Statistika"),
    "lt": ("#EuroLeague", "#Krepšinis", "#Statistika"),
}

DISCLOSURE = {
    "en": "Disclosure: I build catchandstats.com, a free EuroLeague analytics site. "
    "The numbers above come from it.",
    "el": "Αποκάλυψη: είμαι ο δημιουργός του catchandstats.com, μιας δωρεάν σελίδας "
    "αναλύσεων EuroLeague. Τα νούμερα προέρχονται από εκεί.",
}

MAX_HASHTAGS = {
    "x": 1,
    "instagram": 10,
    "reddit": 0,
    "tiktok": 6,
    "facebook": 3,
    "youtube": 3,
    "linkedin": 3,
    "telegram": 2,
}


def _subject(spec: dict) -> str:
    kind = spec.get("kind")
    title = (spec.get("title") or "Catch & Stats").strip()
    if kind == "metric":
        player = (spec.get("subtitle") or "").split("·")[0].strip()
        return f"{title} — {player}" if player else title
    return title


def _row_label(row: dict, locale: str) -> str:
    if row.get("note_metric"):
        # Recap rows: the label is the player, the note carries the metric.
        return row.get("label") or ""
    key = row.get("key")
    return metric_label(key, locale) if key else (row.get("label") or "")


def _row_note(row: dict, locale: str) -> str:
    """Localise the "Metric · Team" note on recap rows."""
    if row.get("note_metric"):
        return f"{metric_label(row['note_metric'], locale)} · {row.get('note_team', '')}".strip(" ·")
    return row.get("note") or ""


def _body_lines(spec: dict, locale: str = "en", max_rows: int = 5) -> list[str]:
    lines: list[str] = []
    if spec.get("headline"):
        label = (
            metric_label(spec["headline_key"], locale)
            if spec.get("headline_key")
            else spec.get("headline_label", "")
        )
        line = f"{spec['headline']} {label}".strip()
        if spec.get("headline_note"):
            line += f" ({spec['headline_note']})"
        lines.append(line)
    for row in (spec.get("rows") or [])[:max_rows]:
        if "left" in row or "right" in row:
            lines.append(
                f"{_row_label(row, locale)}: {row.get('left', '—')} vs {row.get('right', '—')}"
            )
            continue
        if row.get("team") and row.get("net"):
            record = f" ({row['record']})" if row.get("record") else ""
            lines.append(f"{row['team']}{record} — {row['net']} net")
            continue
        line = f"{_row_label(row, locale)}: {row.get('value', '—')}"
        note = _row_note(row, locale)
        if note:
            line += f" — {note}"
        lines.append(line)
    return lines


def _tags(locale: str, platform: str) -> list[str]:
    count = MAX_HASHTAGS.get(platform, 2)
    return list(HASHTAGS.get(locale, HASHTAGS["en"])[:count])


def _x_draft(hook: str, body: list[str], link: str, tags: list[str], limit: int = 280) -> str:
    """Fit as many numbers as the X budget allows, never the hook.

    A link is preferred, but a bare brand mention is what usually survives —
    which is fine: on X the link belongs in the first reply anyway.
    """
    tail = " ".join(tags)
    brand = "catchandstats.com"
    parts = [hook]
    for line in body[:4]:
        probe = "\n".join([*parts, line, link or brand, tail])
        if len(probe) <= limit:
            parts.append(line)
    for ending in ([link] if link else []) + [brand, ""]:
        text = "\n".join(part for part in [*parts, ending, tail] if part)
        if len(text) <= limit:
            return text
    text = "\n".join(parts)
    return text[: limit - 1].rstrip() + "…" if len(text) > limit else text


def _x_thread(hook: str, body: list[str], link: str, tags: list[str], limit: int = 280) -> list[str]:
    """Turn a table into an 8-10 tweet thread, one number per tweet.

    X is where the Top 8 table travels best, but one 280-character post cannot
    hold eight clubs. The thread keeps the hook and the CTA and sends the middle
    rows as replies; the first tweet is still the standalone draft.
    """
    tweets = [hook]
    for line in body[:8]:
        candidate = f"{len(tweets)}/ {line}"
        if len(candidate) > limit:
            candidate = candidate[: limit - 1].rstrip() + "…"
        tweets.append(candidate)
    cta = f"Full profiles and definitions: {link}" if link else "Full data: catchandstats.com"
    if len(cta) > limit:
        cta = "Full data: catchandstats.com"
    tweets.append(cta)
    if tags:
        first = f"{tweets[0]} {' '.join(tags)}".strip()
        if len(first) <= limit:
            tweets[0] = first
    return tweets


def _fit(sections: list[str], limit: int, separator: str = "\n\n") -> str:
    """Drop the least important section until the draft fits the platform."""
    sections = [section for section in sections if section]
    while len(sections) > 1 and len(separator.join(sections)) > limit:
        # Never drop the hook (index 0); drop from the end (link/CTA/tags last).
        sections.pop(-2 if len(sections) > 2 else -1)
    text = separator.join(sections)
    if len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return text


def _reddit(spec: dict, locale: str, link: str) -> tuple[str, str]:
    subject = _subject(spec)
    hook = HOOKS.get(spec.get("kind", "player"), HOOKS["player"]).get(locale, HOOKS["player"]["en"])
    title = hook.format(subject=subject)
    if len(title) > 300:
        title = f"{subject} — the numbers behind it"
    body = [f"{line}" for line in _body_lines(spec, locale, max_rows=10)]
    tail = DISCLOSURE.get(locale, DISCLOSURE["en"])
    sections = [*body, tail]
    if link:
        sections.append(f"Full data: {link}")
    return title[:300], _fit(sections, LIMITS["reddit"])


def build_captions(
    spec: dict,
    link: str = "",
    platforms: tuple[str, ...] | list[str] | None = None,
    locales: tuple[str, ...] | list[str] | None = None,
    links: dict[str, str] | None = None,
    hashtags: dict[str, list[str]] | None = None,
) -> list[dict]:
    """Draft every requested platform × language combination.

    ``links`` lets each platform get its own UTM-tagged URL; ``link`` is the
    fallback. Reddit gets no tracked link unless one is passed explicitly,
    because a naked tracking URL in a text post reads like an ad.

    ``hashtags`` is an optional bank keyed by ``"platform:locale"`` (or just
    ``locale``). When it is supplied the bank replaces the built-in three tags;
    a caller can therefore keep the plan's 8-12 Instagram tags without changing
    this module.
    """
    kind = spec.get("kind", "player")
    if kind not in HOOKS:
        kind = "player"
    subject = _subject(spec)
    hook_templates = HOOKS[kind]
    chosen_platforms = tuple(platforms or PLATFORMS)
    chosen_locales = tuple(locales or LOCALES)

    drafts: list[dict] = []
    for platform in chosen_platforms:
        if platform not in LIMITS:
            continue
        if links is None:
            platform_link = link
        else:
            # An explicit ``links`` map is authoritative: a platform missing
            # from it (Reddit, by design) gets no URL at all.
            platform_link = links.get(platform, "")
        for locale in chosen_locales:
            if locale not in LOCALES:
                continue
            hook = hook_templates.get(locale, hook_templates["en"]).format(subject=subject)
            body = _body_lines(spec, locale)
            if hashtags:
                tags = list(hashtags.get(f"{platform}:{locale}") or hashtags.get(locale) or _tags(locale, platform))
            else:
                tags = _tags(locale, platform)
            tags = tags[: MAX_HASHTAGS.get(platform, 2)]
            cta = (CTAS if platform_link else CTA_NO_LINK).get(locale, CTAS["en"])
            cta = cta.format(link=platform_link) if platform_link else cta
            title = ""
            thread: list[str] = []

            if platform == "reddit":
                title, text = _reddit(spec, locale, platform_link)
            elif platform == "x":
                text = _x_draft(hook, body, platform_link, tags)
                thread = _x_thread(hook, _body_lines(spec, locale, max_rows=8), platform_link, tags)
                if thread:
                    text = thread[0]
            elif platform == "tiktok":
                sections = [hook, "\n".join(body[:2]), "Full breakdown → link in bio.", " ".join(tags)]
                text = _fit(sections, LIMITS["tiktok"])
            elif platform == "youtube":
                title = _truncate_text(hook, 100)
                sections = [hook, "\n".join(body[:5]), cta, " ".join(tags)]
                text = _fit(sections, LIMITS["youtube"])
            elif platform in ("facebook", "linkedin"):
                sections = [hook, "\n".join(body[:5]), cta, " ".join(tags)]
                text = _fit(sections, LIMITS[platform])
            elif platform == "telegram":
                sections = [hook, "\n".join(body[:5]), cta, " ".join(tags)]
                text = _fit(sections, LIMITS["telegram"])
            else:  # instagram
                sections = [hook, "\n".join(body[:5]), cta, " ".join(tags)]
                text = _fit(sections, LIMITS["instagram"])

            draft = {
                "platform": platform,
                "locale": locale,
                "title": title,
                "text": text,
                "hashtags": tags,
                "limit": LIMITS[platform],
                "length": len(text),
                "within_limit": len(text) <= LIMITS[platform],
                "localisation": "full" if locale in FULL_LOCALES else "hook",
            }
            if thread:
                draft["thread"] = thread
            drafts.append(draft)
    return drafts


def _truncate_text(text: str, limit: int) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"
