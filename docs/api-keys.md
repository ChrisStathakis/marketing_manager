# API keys

Third-party credentials the backend can use. They are managed in **Settings → API keys**
(or **API keys & integrations** in the UI) or via `backend/.env`; the app works without any
of them (the related feature just stays off).

## How credentials are handled

- **Precedence:** an explicit `api_key` in a request body → a credential saved in Settings
  (database) → the environment variable from `backend/.env`.
- **Storage:** saved secrets are encrypted at rest (Fernet, key derived from `DJANGO_SECRET_KEY`)
  in the `IntegrationCredential` table. The API returns configuration status only — never the
  secret value.
- **Write-only:** once saved, a secret can be replaced or removed, but it is never displayed
  again. A short display hint is kept (for a plain key, its last four characters; for a
  service-account key file, its `client_email`) so you can tell which credential is active.
- **Fields:** each integration declares which inputs it needs. Secret inputs go into the
  encrypted blob; non-secret *settings* (a GA4 property id, an Ads customer id, …) are stored
  as plain JSON and **are** returned by the status API so the UI can pre-fill them.
- **Permissions:** only staff users (`is_staff`) can save or remove credentials, and only they
  can trigger a sync. Any signed-in user can read the status list.
- **Rotation caveat:** rotating `DJANGO_SECRET_KEY` makes saved secrets unreadable. The Settings
  card flags them as *Needs attention* — remove the entry and save the value again.

## OpenAI (`OPENAI_API_KEY`)

| | |
| --- | --- |
| Powers | “Generate AI” suggestions on a campaign |
| Endpoint | `POST /api/suggestions/generate-ai/` |
| Where to get it | https://platform.openai.com/api-keys |
| Env fallback | `OPENAI_API_KEY` in `backend/.env` |

Steps: sign in at platform.openai.com → *API keys* → *Create new secret key* (starts with `sk-`
and is shown only once) → paste it in Settings → API keys, or set `OPENAI_API_KEY` in
`backend/.env` and restart Django. Set a low usage limit on the key — suggestions only make
small requests.

Without a key, rule-based suggestions (`POST /api/suggestions/generate/`) still work.

## Google Analytics 4 (`GOOGLE_ANALYTICS_CREDENTIALS`, `GOOGLE_ANALYTICS_PROPERTY_ID`)

| | |
| --- | --- |
| Powers | Daily revenue/orders imported per campaign (no more CSV) |
| Endpoints | `POST /api/integrations/google-analytics/sync/`, `manage.py sync_google` |
| Env fallbacks | `GOOGLE_ANALYTICS_CREDENTIALS` (the whole key file, as JSON), `GOOGLE_ANALYTICS_PROPERTY_ID` |

Auth uses a **service account**: the backend signs a JWT with the key file’s private key and
exchanges it for an access token (`cryptography` + `urllib` — no extra SDKs).

Steps:

1. In Google Cloud, create (or reuse) a project and enable the **Google Analytics Data API**.
2. Create a **service account**, add a **JSON key** and download it.
3. In GA4 → **Admin → Property access management**, add the service-account email
   (`…@….iam.gserviceaccount.com`) as **Viewer**.
4. In Settings → API keys, paste the **whole JSON key file** and the **GA4 property ID**
   (GA4 → Admin → Property settings → Property ID, digits only) — or set the two env vars above.
5. Click **Sync now** (or run the command below).

What a sync writes:

- Daily `revenue` (`totalRevenue`) and `orders` (`transactions`) per **`sessionCampaignName`**,
  matched case-insensitively against `Campaign.utm_campaign`.
- Rows that match **no** campaign are *not* dropped silently: the response lists them under
  `unmatched` and the UI shows them, so you can fix the UTM or the campaign.
- Placeholders (`(not set)`, `(direct)`, `(referral)`, …) are skipped.
- GA4 has **no ad cost**, so `spend`, `ctr` and ROAS are never touched by a sync; revenue is
  stored and ROAS is recomputed from whatever spend the row already has.
- Rows are marked `source = "ga4"` (`DailyMetric.source`). Re-running is idempotent — the last
  7 days are refreshed by default (`?days=` / `--days` override, max 365).

Cron example (daily, shortly after midnight, refreshing the last week):

```powershell
cd backend
..\.venv\Scripts\python.exe manage.py sync_google --days 7
```

Sync results are recorded on the credential row (`last_synced_at`, `last_sync_error`) and shown
in Settings. A key coming purely from `backend/.env` has no row to record against, so those two
fields stay empty.

## Instagram (`INSTAGRAM_SESSIONID`, `INSTAGRAM_USERNAME`, `INSTAGRAM_PROXY`)

| | |
| --- | --- |
| Powers | Who commented on a **public** post (audience research) |
| Endpoints | `POST /api/growth/instagram/test/`, `POST /api/growth/instagram/posts/{id}/scrape/` |
| Env fallbacks | `INSTAGRAM_SESSIONID`, `INSTAGRAM_USERNAME`, `INSTAGRAM_PROXY` |

!!! warning "Not official API usage"
    In 2026 Instagram serves post data **only** to logged-in sessions (anonymous requests get
    `429` or `401 require_login`), so this reads the comments endpoint with the **`sessionid`
    cookie** of a logged-in account. It is unofficial: it can break without notice and risks
    action against that account. **Likers are not available by any method** — this returns
    commenters only. Treat the cookie like a password and use a throwaway account.

How it works: the shortcode in a post URL is decoded to a media id **locally**, so no profile
lookup is needed; only the comments endpoint is called, with the cookie.

Steps:

1. Log in to Instagram in a browser — a **burner** account is recommended.
2. DevTools → **Application → Cookies → `https://www.instagram.com`**, copy the **`sessionid`** value.
3. In Settings → API keys, paste it (or set `INSTAGRAM_SESSIONID` in `backend/.env`), then use
   **Test connection** — it reports which account the cookie belongs to.
4. Optionally set a **proxy** to avoid rate limits on your own IP.

Caveats:

- Cookies expire: a `401` means log in again and paste a fresh one.
- Keep the feature behind `INSTAGRAM_SCRAPER_ENABLED` (set it to `False` to turn the section
  off); `INSTAGRAM_MAX_COMMENTS` caps how many comments one scrape pulls, and
  `INSTAGRAM_TIMEOUT` / `INSTAGRAM_API_BASE` override the rest.
- Commenter usernames are **personal data**. Only collect what you need, keep it no longer than
  necessary, and do not use it for unsolicited outreach.
- CLI equivalent: `manage.py instagram_check [--url …] [--limit N]`.

## API

See `docs/api-reference.md` → Integrations.
