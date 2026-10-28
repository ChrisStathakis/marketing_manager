"""The seeded Top 8 launch playbook.

The PDF that started this is a good campaign, not a good database row: it names
dates in October 2026 and hardcodes seven rounds. This module keeps the *shape*
β€” fourteen days, cover + eight team checks, the priority subreddits, the paid
test β€” and throws the dates away. A run supplies the start date and round label.

The copy here is a brief, not a finished caption. The card studio and caption
builder own the final wording; this is the editorial plan a human approves.
"""

from __future__ import annotations

from datetime import time

from .models import HashtagSet, Playbook, PlaybookSlot

PLAYBOOK_NAME = "Top 8 launch β€” 14 days"

DESCRIPTION = (
    "A 14-day EuroLeague Top 8 launch. Hero asset: an Instagram carousel with a "
    "cover, one four-factors slide per team and a CTA. Priority platforms: "
    "Instagram, Reddit and X; repurpose to TikTok, Facebook and YouTube. The "
    "Top 8 is ranked by record, then net rating; every team slide compares this "
    "season with last season. No dates are stored in the template β€” each run "
    "creates a new campaign from the start date you choose."
)

#: (day offset, HH:MM, platform, format, content kind, locales, title, brief,
#:  utm_content template, asset required, task only)
_SLOTS = [
    (0, "20:00", "tiktok", "photo_carousel", "top8", ["el"], "Top 8 photo carousel β€” {round}",
     "Cover + 8 team slides. Use the same 1080Γ—1350 frames as the Instagram carousel; add the table as slide 2 if it fits.",
     "photo_carousel_el", True, False),
    (0, "21:00", "instagram", "carousel", "top8", ["el"], "Top 8 carousel β€” {round}",
     "9β€“10 slides: hook, eight team checks (record + net rating + last season), CTA. Hook: Β«7 Ξ±Ξ³Ο‰Ξ½ΞΉΟƒΟ„ΞΉΞΊΞ­Ο‚. 8 ΞΏΞΌΞ¬Ξ΄ΞµΟ‚. Ξ ΞΏΞΉΞ± ΞΊΟΞ±Ο„Ξ¬ΞµΞΉ;Β» Keep the first slide text under 12 words.",
     "carousel_el", True, False),
    (0, "21:30", "instagram", "story", "top8", ["el"], "Top 8 stories β€” {round}",
     "Three frames: the table, the biggest net-rating jump, and a poll: Β«Ξ ΞΏΞΉΞ± ΞΏΞΌΞ¬Ξ΄Ξ± Ξ­Ο‡ΞµΞΉ Ο„ΞΏ ΞΊΞ±Ξ»ΟΟ„ΞµΟΞΏ net rating;Β» Link the carousel in the last frame.",
     "story_el", True, False),
    (0, "22:00", "x", "thread", "top8", ["el"], "Top 8 thread β€” {round}",
     "Eight tweets plus a CTA: one team per tweet, record then net rating. Do not put the link in tweet 1; put it in the last tweet.",
     "thread_el", False, False),
    (1, "08:30", "reddit", "text_post", "top8", ["en"], "r/Euroleague β€” Top 8 after {round}",
     "Original data post. Title is the hook, body is the table plus one sentence on the method. Disclose that you build catchandstats.com. No naked UTM link; put the source in a comment if asked.",
     "reddit_top8", True, False),
    (1, "12:00", "instagram", "reel", "top8", ["el"], "Top 8 Reel β€” {round}",
     "15-second vertical cut: cover β†’ top three teams β†’ CTA. Use the carousel frames as stills if there is no footage.",
     "reel_el", True, False),
    (1, "18:00", "x", "post", "top8", ["el"], "Top 8 quote β€” {round}",
     "Quote the thread with the single most surprising number (biggest net-rating gap or the best 4β€“3 team).",
     "quote_el", False, False),
    (1, "20:00", "facebook", "post", "top8", ["el"], "Top 8 Facebook β€” {round}",
     "Link post with the table image. Short hook, three sentences, one question. 3 hashtags maximum.",
     "facebook_el", True, False),
    (2, "09:00", "reddit", "text_post", "team", ["el"], "r/Panathinaikos β€” Pana check",
     "Greek-language post for the club subreddit. One table, one observation, no cross-posting spam. Disclose the site.",
     "reddit_pana", True, False),
    (2, "20:30", "tiktok", "photo_carousel", "team", ["el"], "Pana photo carousel",
     "Team card + last season comparison + one line on what changed. 1080Γ—1350.",
     "photo_pana_el", True, False),
    (2, "21:00", "instagram", "post", "team", ["el"], "Pana check",
     "Single team card. Net rating is the headline; ORtg, DRtg, TS%, eFG%, TOV% are the support. Mention the record.",
     "team_pana_el", True, False),
    (2, "22:00", "x", "post", "team", ["en"], "Pana chart",
     "English chart/card. One sentence on the delta from last season; ask what the first-round sample is missing.",
     "team_pana_en", False, False),
    (3, "09:00", "reddit", "text_post", "team", ["el"], "r/OlympiacosBC β€” Oly check",
     "Same structure as the Pana post, different subreddit. Do not reuse the Pana title.",
     "reddit_oly", True, False),
    (3, "20:00", "facebook", "post", "team", ["el"], "Oly Facebook",
     "Club-level post with the team card. Link to the full profile; keep the copy short.",
     "team_oly_fb", True, False),
    (3, "21:00", "instagram", "post", "team", ["el"], "Oly check",
     "Single team card, Greek. Lead with the defensive rating and the record, not the sponsor name.",
     "team_oly_el", True, False),
    (3, "22:00", "x", "post", "team", ["en"], "Oly chart",
     "English chart. Compare the defensive rating with last season; one number is enough.",
     "team_oly_en", False, False),
    (4, "20:00", "tiktok", "photo_carousel", "top8", ["en"], "Top 8 photo carousel β€” English",
     "English translation of the day-0 photo carousel. Change the hook, not just the caption.",
     "photo_carousel_en", True, False),
    (4, "21:00", "instagram", "carousel", "top8", ["en"], "Top 8 carousel β€” English",
     "English version of the hero carousel. Rebuild the caption from the English table; do not machine-translate the Greek hook.",
     "carousel_en", True, False),
    (4, "22:00", "x", "thread", "top8", ["en"], "Top 8 thread β€” English",
     "English thread. Same eight teams, same order; the CTA can point to the English landing copy.",
     "thread_en", False, False),
    (5, "20:00", "youtube", "video", "top8", ["en"], "Top 8 video breakdown",
     "60-second vertical/horizontal cut for YouTube Shorts and the channel: hook, top three teams, method, CTA. Do not re-use the Instagram caption verbatim.",
     "video_en", True, False),
    (5, "21:00", "instagram", "story", "top8", ["el"], "Top 8 stories β€” poll and quiz",
     "Poll: which team is the real contender? Quiz: which team has the best net rating? Use the answer frame to link the table.",
     "story_poll_el", True, False),
    (6, "20:00", "tiktok", "photo_carousel", "top8", ["el"], "Round 8 update β€” photo carousel",
     "Refresh the table after Round 8. Replace the team slides that changed; do not repost the Round 7 carousel unchanged.",
     "photo_round8_el", True, False),
    (6, "21:00", "instagram", "carousel", "top8", ["el", "en"], "Round 8 update β€” carousel",
     "Two-language refresh. Lead with what changed since Round 7: one climber, one faller, one unchanged leader.",
     "carousel_round8", True, False),
    (6, "22:00", "x", "thread", "top8", ["en"], "Round 8 thread",
     "Thread the changes, not the whole table again: three tweets maximum, then the full-table link.",
     "thread_round8_en", False, False),
    (7, "20:30", "tiktok", "photo_carousel", "team", ["el"], "Crvena / Valencia photo",
     "Pick the more interesting of the two team cards; do not publish two near-identical posts on the same day.",
     "photo_crvena_el", True, False),
    (7, "21:00", "instagram", "post", "team", ["el"], "Crvena / Valencia check",
     "Team card with the bigger season-over-season delta. One observation about style of play, one number.",
     "team_crvena_el", True, False),
    (7, "22:00", "x", "post", "team", ["en"], "Crvena chart",
     "English chart. Focus on the defensive number if it is the outlier.",
     "team_crvena_en", False, False),
    (8, "21:00", "instagram", "post", "team", ["el"], "Fener / Real check",
     "Team card for the club with the better story. FenerbahΓ§e if the net rating holds; Real if the record overstates the performance.",
     "team_fener_el", True, False),
    (8, "22:00", "x", "post", "team", ["en"], "Fener chart",
     "English chart. One sentence on the gap between record and net rating.",
     "team_fener_en", False, False),
    (9, "21:00", "instagram", "reel", "top8", ["en"], "Top 8 Reel β€” English",
     "15-second English cut. Use the same edit as the Greek reel with new captions; keep the CTA identical.",
     "reel_en", True, False),
    (9, "20:30", "linkedin", "post", "top8", ["en"], "Top 8 for analysts β€” LinkedIn",
     "Analyst angle: what the table says about roster construction and shot quality, not a fan argument. One chart, three observations, no hashtag wall.",
     "linkedin_analysts", True, False),
    (9, "22:00", "x", "thread", "top8", ["en"], "Top 8 recap thread",
     "A recap, not a repeat: what the table looked like on day 0, what changed, and what to watch next round.",
     "thread_recap_en", False, False),
    (10, "20:00", "tiktok", "photo_carousel", "top8", ["el"], "Best-of photo carousel",
     "Best-of: the three most-saved team slides and the one number people argued about. Ask for the next team to cover.",
     "photo_bestof_el", True, False),
    (10, "21:00", "instagram", "carousel", "top8", ["el"], "Best-of carousel",
     "Best-of carousel. Lead with the best-performing team slide; close with the CTA and the next-round promise.",
     "carousel_bestof_el", True, False),
    (11, "21:00", "instagram", "story", "top8", ["el"], "Stories Q&A",
     "Answer three questions from the comments. Each answer is one frame; the last frame links the table.",
     "story_qa_el", True, False),
    (13, "10:00", "other", "other", "", ["en"], "Review KPIs and decide the next run",
     "Review the targets on the campaign: saves, shares, profile visits, link clicks, signups, Reddit upvote ratio, X impressions. Decide whether to repeat the hero carousel or change the hook. Then run the playbook again with a new start date and round label.",
     "review", False, True),
]

HASHTAG_BANKS = [
    {
        "name": "Top 8 β€” Greek",
        "locale": "el",
        "tags": [
            "#EuroLeague", "#Ξ•Ο…ΟΟ‰Ξ»Ξ―Ξ³ΞΊΞ±", "#ΞΟ€Ξ¬ΟƒΞΊΞµΟ„", "#Top8", "#EuroLeagueGR",
            "#Ξ Ξ±Ξ½Ξ±ΞΈΞ·Ξ½Ξ±ΟΞΊΟΟ‚", "#ΞΞ»Ο…ΞΌΟ€ΞΉΞ±ΞΊΟΟ‚", "#BasketballAnalytics",
            "#ΞΞ±Ξ»Ξ±ΞΈΞΏΟƒΟ†Ξ±Ξ―ΟΞΉΟƒΞ·", "#EuroleagueBasketball", "#AdvancedStats", "#Top8EuroLeague",
        ],
    },
    {
        "name": "Top 8 β€” English",
        "locale": "en",
        "tags": [
            "#EuroLeague", "#EuroLeagueStats", "#BasketballAnalytics", "#Top8",
            "#Basketball", "#EuroleagueBasketball", "#AdvancedStats", "#NetRating",
            "#FourFactors", "#DataVisualization",
        ],
    },
    {
        "name": "Top 8 β€” Turkish",
        "locale": "tr",
        "tags": ["#EuroLeague", "#Basketbol", "#Δ°statistik", "#Top8", "#FenerbahΓ§e", "#AnadoluEfes"],
    },
    {
        "name": "Top 8 β€” Serbian",
        "locale": "sr",
        "tags": ["#EuroLeague", "#KoΕ΅arka", "#Statistika", "#Top8", "#CrvenaZvezda", "#Partizan"],
    },
    {
        "name": "Top 8 β€” Lithuanian",
        "locale": "lt",
        "tags": ["#EuroLeague", "#KrepΕ΅inis", "#Statistika", "#Top8", "#Ε½algiris"],
    },
]


def _slot_rows():
    for order, row in enumerate(_SLOTS):
        (
            day_offset, clock, platform, fmt, kind, locales, title, brief, utm, asset, task_only,
        ) = row
        yield {
            "order": order,
            "day_offset": day_offset,
            "time": time.fromisoformat(clock),
            "platform": platform,
            "format": fmt,
            "content_kind": kind,
            "locales": locales,
            "title_template": title,
            "brief": brief,
            "utm_content_template": utm,
            "asset_required": asset,
            "paid_budget": 150 if (day_offset == 0 and platform == "instagram" and fmt == "carousel") else 0,
            "is_task_only": task_only,
        }


def seed_top8_playbook(force: bool = False) -> tuple[Playbook, bool]:
    """Create the seeded playbook and hashtag banks. Safe to call repeatedly."""
    playbook, created = Playbook.objects.get_or_create(
        name=PLAYBOOK_NAME,
        defaults={
            "description": DESCRIPTION,
            "default_locales": ["el", "en"],
            "default_platforms": ["instagram", "x", "tiktok", "reddit", "facebook", "linkedin", "youtube"],
            "is_seeded": True,
        },
    )
    if force or created:
        playbook.description = DESCRIPTION
        playbook.default_locales = ["el", "en"]
        playbook.default_platforms = ["instagram", "x", "tiktok", "reddit", "facebook", "linkedin", "youtube"]
        playbook.is_seeded = True
        playbook.save()
        playbook.slots.all().delete()
        for row in _slot_rows():
            PlaybookSlot.objects.create(playbook=playbook, **row)

    for bank in HASHTAG_BANKS:
        HashtagSet.objects.get_or_create(
            name=bank["name"],
            locale=bank["locale"],
            platform="",
            defaults={"tags": bank["tags"], "is_default": True},
        )
    return playbook, created
