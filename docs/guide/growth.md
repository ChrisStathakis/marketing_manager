# Growth studio

The growth studio turns the public numbers on **catchandstats.com** into things you can post:
a share image, a caption in five languages, and next week's calendar. It is built for one
person with two to four hours a week and no ad budget.

It never publishes anything. It reads the public API, writes drafts, and stops. You press send.

!!! info "Read-only by design"
    The studio only calls the public JSON endpoints that the site itself uses. Nothing here
    writes to catchandstats.com, and no account credentials for X, Reddit, TikTok or Telegram
    are stored anywhere. The one exception is the optional **Instagram comment research**
    section (8), which uses a `sessionid` cookie from a throwaway Instagram account — see
    *Instagram comment research* below.

## The weekly rhythm

| Day | Post | Why |
| --- | --- | --- |
| Monday | **Round recap** — five numbers from the round | People are already talking about the games; give them a number they did not see. |
| Tuesday | **Metric of the day** — one proprietary metric | This is the moat: consistency, home-court swing, fantasy ceiling. |
| Wednesday | **Head to head** — two players, same metrics | Invites disagreement, which is what replies are made of. |
| Friday | **Post-round numbers** — one player card | Fresh data after the mid-week games. |
| Sunday | **Weekly digest** — recap + links | Retention: the people who already follow you. |

**Fill the calendar** creates all eight slots (including the Instagram carousel, the Reddit
value post, the TikTok short and the Telegram digest) as scheduled content items, plus a to-do
for each one. Run it once a week; run it twice and it skips what already exists.

## Building a card

1. Open **Growth studio** in the sidebar.
2. Pick a **card type**, a **market** (or leave it on *All markets*), and optionally a **metric**
   or a specific **player**.
3. Press **Draft a card**. The studio picks the rest: the player, the number, and the wording.
4. Change **Format** to get the same story at another size. Nothing is re-written.

| Card type | What it shows |
| --- | --- |
| **Player card** | One player, the overall rating as the headline, four supporting numbers. |
| **Metric of the day** | One number, its label, the player's rank in the league, and context. |
| **Head to head** | Two players, one row per metric, the better number highlighted. |
| **Round recap** | Five different players, each leading a different metric. |
| **Team matchup** | Two clubs compared on offense, defense, pace and fantasy points. |

!!! tip "Avoid the 2-minute cameo"
    Rankings require at least 3 games and 10 minutes per game, and reject impossible values
    (a 150% true-shooting night is a data artefact, not a story). Early in a season the filter
    relaxes rather than showing an empty card. A dash (—) on a card means "not enough signal",
    not "zero".

### Formats and sizes

| Format | Size | Use |
| --- | --- | --- |
| `x` | 1600×900 | X / Twitter, also fine for a LinkedIn-style post |
| `instagram` | 1080×1350 | Instagram feed carousel cover |
| `story` | 1080×1920 | Stories, TikTok and YouTube Shorts cover |
| `reddit` | 1200×1200 | Reddit image posts |
| `og` | 1200×630 | Link previews |

**Save** stores the PNG in the media library and the exact numbers behind it, so a card can be
regenerated later with **Copy** on `/api/cards/{id}/recaption/`. **PNG** downloads the file.

## Captions

Every card produces drafts for X, Instagram, Reddit, TikTok and Telegram, in English, Greek,
Turkish, Serbian and Lithuanian.

| Language | Draft quality |
| --- | --- |
| English | Full |
| Greek | Full — the site's second language |
| Turkish, Serbian, Lithuanian | Native hook and call to action around an English body |

Character counters show the real limit per platform (280 on X). If a draft is too long the
studio drops supporting lines before it drops the hook.

!!! warning "Reddit drafts deliberately contain no tracking link"
    A naked UTM URL in a text post reads like an advert and trips the self-promotion rules.
    The draft leads with the numbers, discloses that you build the site, and names it. Add a
    link only where the subreddit's rules allow it.

## Markets

The priority markets are Greece, Türkiye, Serbia and Lithuania. Filtering by market restricts
auto-picks to clubs from that country:

| Market | Clubs in the data |
| --- | --- |
| Greece | Olympiacos, Panathinaikos |
| Türkiye | Fenerbahçe, Anadolu Efes, Beşiktaş |
| Serbia | Crvena Zvezda, Partizan |
| Lithuania | Žalgiris |

AEK, Aris and PAOK are not in the EuroLeague dataset, so the studio cannot build club cards for
them. Those audiences are still reachable through league-wide posts and the national-language
hooks.

## Logging what worked

**5. What worked** is the only scoreboard that matters: posts, impressions, clicks, click rate
and engagement per platform, plus the same numbers broken down by card type and by metric.
Every rate is shown against the equivalent window before it, so a good week and a good trend
are different columns. Log a post after it has been up for a day:

| Field | Notes |
| --- | --- |
| Platform | Where it went |
| Date | Used for the 7/30/90-day window |
| Impressions | Reach, as reported by the platform |
| Engagements | Likes + upvotes + saves + shares |
| Clicks | Link clicks, from the platform or GA4 |
| Link | The post URL, for finding it again |
| Card type | Optional — powers the by-type ranking |
| Metric | Optional — powers the by-metric ranking |

Follower counts are deliberately not a field. Referral sessions, branded searches and returning
visitors are what the plan optimises; the report is where they show up first.

## Where the traffic came from

**6. Where the traffic came from** is the other half of the picture: what was published versus
what actually arrived. It reads GA4 sessions per source and maps them back onto the platforms
(`x`, `t.co` → X; `reddit.com` → Reddit; `l.instagram.com` → Instagram), so a post can be judged
on visits, not on how loud the platform's own counter was.

- Requires the existing **Google Analytics** integration (Settings → API keys): the
  service-account JSON plus the GA4 property ID.
- Press **Sync GA4** in the studio, or run `python manage.py sync_google --organic` on the
  server (defaults to the last 30 days for traffic). Syncing is idempotent per day and source.
- Referral links should carry `utm_source` / `utm_medium`; the studio already puts them on the
  X, Instagram, TikTok and Telegram drafts. A platform with clicks but no sessions is a broken
  link or a missing parameter, not a quiet audience.

## What to do next

**7. What to do next** turns the same numbers into a short list of decisions, with the evidence
attached so you can disagree with it:

| Rule | What it means |
| --- | --- |
| *Traffic leak* | A platform produced clicks but GA4 saw no sessions: check the link. |
| *Best channel* | One platform converts impressions to clicks clearly better than the rest. |
| *Best card type / metric* | Same platform, same audience — the difference is the subject. |
| *Reach without clicks* | A post travelled far and converted badly: the hook stopped them, the promise did not. |
| *Unlogged traffic* | GA4 shows sessions from a platform with no post records. |
| *Behind cadence* | Fewer posts than the weekly rhythm. |
| *Stale experiment* | Something has been "running" for three weeks without a verdict. |

Each recommendation can be applied with **Use**, which sets the card type and metric in the
builder and drafts the card immediately. The rules only fire once there is enough data
(at least two posts per group, 200 impressions per platform), so an empty table produces a
short list rather than confident nonsense.

## Instagram comment research

**8. Instagram commenters (research)** answers a different question: *who* is talking about a
post you did not write. Paste a **public** post URL, press **Track post**, then **Scrape** to
pull its comments. The studio stores each commenter and keeps them: re-scraping refreshes the
text and likes without creating duplicates, so a post becomes a small history rather than a
one-off lookup.

Everything is read-only toward Instagram, but this is **not official API usage** and it comes
with caveats worth reading:

- Instagram stopped serving post data to logged-out requests in 2026, so this needs the
  `sessionid` cookie of a **logged-in account**. Use a throwaway — see
  [API keys](../api-keys.md#instagram-instagram_sessionid-instagram_username-instagram_proxy).
- **Likers are not available by any method.** Only commenters.
- It is unofficial and can break or get the account rate-limited (`429`) or logged out (`401`).
  Keep the number of comments per scrape modest and add a proxy if you scrape often.
- Commenter usernames are **personal data**. Collect only what you need, keep it no longer than
  necessary, and **do not use it for unsolicited outreach** — the point is to understand the
  audience, not to message it.

The panel shows totals (comments, commenters, repeat commenters, posts tracked), the most
active accounts, and a per-post breakdown of stored versus reported comments, with **Export CSV**
for the rest of the work.

| Setting | Default | What it does |
| --- | --- | --- |
| `INSTAGRAM_SCRAPER_ENABLED` | `True` | Turn the whole section off |
| `INSTAGRAM_MAX_COMMENTS` | `500` | Cap on comments pulled per scrape |
| `INSTAGRAM_TIMEOUT` | `20` | Per-request timeout in seconds |
| `INSTAGRAM_PROXY` | — | Route requests through a proxy instead of your own IP |
| `INSTAGRAM_API_BASE` | `https://www.instagram.com` | Override for testing only |

## Where the numbers come from

The studio reads `https://catchandstats.com/api` and caches each season on disk for six hours
(`backend/media/growth-cache/`). One season fetch is a handful of requests; regenerating a card
costs none.

Flaky responses are retried (`429`/`5xx`, honouring `Retry-After`); a hard `4xx` or an HTML
error page fails immediately. If a refresh fails and a cache entry exists, the studio serves it
and says so (`stale`) instead of going blank — a day-old table still builds an honest card.

| Setting | Default | What it does |
| --- | --- | --- |
| `CATCHANDSTATS_API_BASE` | `https://catchandstats.com/api` | Point at a staging copy |
| `CATCHANDSTATS_SITE_URL` | `https://catchandstats.com` | Where UTM links point |
| `CATCHANDSTATS_TIMEOUT` | `45` | Per-request timeout in seconds |
| `GROWTH_CACHE_TTL_HOURS` | `6` | How long a season stays cached |
| `GROWTH_CACHE_DIR` | `backend/media/growth-cache` | Where the cache lives |

Season selectors accept any of `6`, `E2026` or `2026-2027`.

## Rules of the road

- **No auto-posting, no bots.** Reddit and X both punish it, and a shadowban costs more than a
  missed post.
- **Reddit: follow the 9:1 rule.** Nine useful comments or posts for every one that mentions
  your site. Disclose that you build it. Read each subreddit's rules first.
- **Never promote `/predictions` on Reddit.** It is betting-adjacent and will get the domain
  banned from the big communities.
- **One proprietary metric per post.** A box score is already everywhere; consistency and
  home-court swing are not.
- **Post the image, not a link**, where links are restricted. The watermark does the work.

## Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| Red banner: *these numbers are cached, not live* | catchandstats.com is down or slow, so the studio fell back to the last cache | Cards still build; press **Draft a card** again later for fresh numbers |
| A card row shows **—** | Value is missing or outside the plausible range | Pick another metric; a dash is intentional |
| **Fill the calendar** lists *missing channels* | No `Channel` exists for that platform | Settings → Channels, add X/Reddit/Instagram/TikTok/Telegram |
| X draft is shorter than expected | The 280-character budget dropped a supporting line | Copy the fuller Instagram draft and trim by hand |
| *Google Analytics is not configured* in section 6 | No GA4 credentials or property ID | Settings → API keys: service-account JSON + property ID |
| **Sync GA4** answers `403` | Not staff, or the service account lacks the property | Run `manage.py sync_google --organic`; check Analytics access |
| Traffic table is empty after a sync | Sessions came from sources the window did not cover, or no sessions yet | Widen the window; remember traffic is stored per day and source |
| **Scrape** answers `400` in section 8 | The sessionid is missing, wrong or expired | Settings → API keys → Instagram: paste a fresh `sessionid`, then **Test session** |
| **Scrape** answers `429` | Instagram is throttling that session | Wait a few minutes; scrape less per run, or set `INSTAGRAM_PROXY` |
| Section 8 says *Instagram research is turned off* | `INSTAGRAM_SCRAPER_ENABLED=False` in `backend/.env` | Set it to `True` and restart the backend |
| Card image does not load in the list | Media files are only served in `DEBUG` | Serve `backend/media/` from the web server in production |

## Next

- [Content & calendar](content-calendar.md) — where the generated posts land.
- [Results & reporting](results.md) — the campaign-level numbers.
- [API reference](../api-reference.md#organic-growth) — the endpoints behind the studio.
