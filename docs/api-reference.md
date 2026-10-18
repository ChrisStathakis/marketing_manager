# API reference

Base `/api/`. Auth: `POST /api/token/`, `POST /api/token/refresh/`, `POST /api/register/` (open until the first account exists — that account becomes the admin; afterwards opt-in with `DJANGO_ALLOW_REGISTRATION=True`; username + password only, no email and no minimum length, returns JWT pair). Authenticated calls use `Authorization: Bearer <access>`.

## Resources

Full CRUD (`GET`, `POST`, `PATCH`, `PUT`, `DELETE` on detail routes):

- `/api/campaigns/`, `/api/channels/`, `/api/content/`, `/api/spend/`, `/api/metrics/`, `/api/tasks/`, `/api/suggestions/`, `/api/products/`, `/api/orders/`, `/api/performance/`, `/api/experiments/`

## Pagination, search and filters

Every list endpoint is paginated: `?page=`, `?page_size=` (default 20, max 500). Responses use the DRF envelope `{count, next, previous, results}`.

| Resource | Search | Ordering | Filters |
| --- | --- | --- | --- |
| campaigns | `name objective utm_campaign` | `created_at start_date budget name` | `status`, `owner` |
| channels | `name handle` | `name` | `channel_type`, `is_active` |
| content | `title copy` | `publish_at id` | `campaign`, `channel`, `status`, `publish_at__gte`, `publish_at__lte` (ISO datetime) |
| tasks | `title notes` | `due_date created_at` | `campaign`, `done`, `suggestion`, `due_date__gte`, `due_date__lte` |
| metrics | — | `date revenue spend` | `campaign`, `date`, `date__gte`, `date__lte` |
| spend | — | `date spend` | `campaign`, `channel`, `date`, `date__gte`, `date__lte` |
| suggestions | — | `created_at` | `campaign`, `kind`, `accepted` |
| products | `name external_id` | `name updated_at` | — |
| orders | — | `ordered_at total` | `campaign`, `utm_source`, `utm_campaign` |

Range filters power the calendar (`content?publish_at__gte=…&publish_at__lte=…`) and reporting (`metrics?date__gte=…&date__lte=…`).

## CSV import / export

- `POST /api/metrics/import-csv/` — file field `file`, columns `campaign,date,revenue,orders,spend,ctr,roas` (roas derived from revenue/spend when omitted).
- `POST /api/spend/import-csv/` — columns `campaign,channel,date,spend,impressions,clicks,conversions`.
- Both import endpoints return `{created, updated, error_count, errors: [{row, error}]}`; invalid rows are skipped and reported with their CSV line number.
- Imported rows are always marked `source="manual"`, so re-importing a CSV overrides a row that a sync produced.
- `GET /api/metrics/export-csv/` and `GET /api/spend/export-csv/` — stream an import-compatible CSV honouring every list filter above (`campaign`, date ranges, channel…). A null channel exports as an empty value.

### Row provenance

`metrics` and `spend` rows carry a read-only `source`: `manual` (default, CSV or UI), `ga4` or
`google_ads` (written by a sync). It is never accepted from clients — posting it is ignored.

## Suggestions

- `POST /api/suggestions/generate/` body `{"campaign": id}` → rule suggestions. Re-running refreshes open suggestions with the same title instead of stacking duplicates.
- `POST /api/suggestions/generate-ai/` body `{"campaign": id, "api_key?": "..."}` → 501 without a key, else stored/refreshed as kind=ai. Key resolution: request `api_key` → key saved in Settings → `OPENAI_API_KEY` env (see [api-keys.md](api-keys.md)).
- `POST /api/suggestions/{id}/accept/` body `{"title?", "due_date?"}` → marks accepted and creates a linked task (idempotent: returns the existing task with `created: false` on repeat).
- `POST /api/suggestions/{id}/reopen/` → moves it back to the open list; any created task is kept.
- The serializer includes the linked `task {id, title, done, due_date}` or `null`.

## Integrations

Third-party credentials (see [api-keys.md](api-keys.md)). Secret values are write-only: stored
encrypted, never returned. Non-secret settings are returned so the UI can pre-fill them.

- `GET /api/integrations/` — any authenticated user. Registry entries (label, summary, description, `env_var`, `used_by`, `where_to_get`, `steps`, `security_note`, `fields`, `config_fields`, optional `sync_endpoint`) plus status: `configured`, `source` (`database` | `env` | `null`), `key_hint`, `stored`, `stored_unreadable`, `config` (non-secret values), `last_synced_at`, `last_sync_error`, `updated_at`, `updated_by`.
- `PUT /api/integrations/{provider}/` — staff only. Body `{"fields": {"<name>": "…"}, "config": {"<name>": "…"}}`; the classic single-key shape `{"key": "…"}` still works for providers whose only field is `key`. Omitted secret fields keep their stored value (so settings can be changed without re-pasting the key); string fields are length-checked, and required settings must resolve (store or `env_var`). Response is the same status object, never a secret.
- `DELETE /api/integrations/{provider}/` — staff only; removes the stored credential, so the `env_var` fallback (if set) becomes active again.
- Unknown provider slugs → 404. Unknown body keys are ignored; an unsupported `key` shape → 400.

### Google Analytics sync

- `POST /api/integrations/google-analytics/sync/` — staff only. Body `{"days"?: 1..365}` (default 7).
  Pulls `totalRevenue` / `transactions` per day and `sessionCampaignName` from the GA4 Data API and
  upserts daily metrics matched on `Campaign.utm_campaign`.
  Returns `{created, updated, skipped, rows, unmatched: [str], start, end, last_synced_at}`.
  - `400` when the integration is not configured (missing key file or property ID), or `days` is invalid.
  - `502` when Google refuses the request; the message is stored in `last_sync_error`.
  - Only `revenue`, `orders`, `roas` and `source` are written — `spend`/`ctr` are left alone (GA4 has no ad cost).
  - Equivalent CLI: `manage.py sync_google --days 7`.

## Dashboard

`GET /api/dashboard/summary/` — totals (`spend`, `revenue`, `orders`, `roas`), `deltas` vs the previous same-length window (percent, `null` when there is no basis), a daily `series` of revenue/spend/orders, the resolved `range`, and the top-20 `campaigns` breakdown.

- `?days=N` — last N days ending today, e.g. `?days=30`.
- `?date__gte=YYYY-MM-DD&date__lte=YYYY-MM-DD` — explicit range (overrides `days` when `date__gte` is given).
- No params → all time (deltas are `null`).

## Organic growth

Tools for the read-only growth workflow around catchandstats.com: build a share image from the
public season data, draft captions, and seed the calendar. Nothing is published from here.

Season parameters accept a season primary key (`6`), the API code (`E2026`) or the title
(`2026-2027`). Season data is cached on disk for six hours by default
(`GROWTH_CACHE_TTL_HOURS`); see `CATCHANDSTATS_API_BASE`, `CATCHANDSTATS_SITE_URL`,
`CATCHANDSTATS_TIMEOUT` and `GROWTH_CACHE_DIR`.

Reads are hardened: transient HTTP statuses (`408`, `425`, `429`, `5xx`) are retried up to three
times honouring `Retry-After`, other `4xx` and non-JSON bodies fail immediately, and a failed
refresh falls back to the cached season with `stale: true` and an explanatory `warning` instead
of an error (truncated pagination is reported the same way).

- `GET /api/growth/meta/` — seasons, default season, priority markets and clubs, card kinds,
  formats and sizes, platforms, locales, the metric catalogue, the resolved site URL, the
  `sources` map (GA4 session source → platform), `ga4_configured` and `can_sync`.
  Returns `warning` (and an empty season list) when the public API is unreachable.
- `GET /api/growth/players/` — picker data for the selected season. Filters: `season`,
  `search` (player or club), `country` (`GR`, `TR`, `RS`, `LT`) and `metric`;
  `ordering` = `-<metric>` or `player`; `page`, `page_size` (max 200). Returns
  `{count, page, page_size, season, fetched_at, stale, warning, teams, results}`.
- `GET /api/growth/suggest/` — picks the next card. Parameters: `kind` (`player`, `metric`,
  `comparison`, `round_recap`, `matchup`), `season`, `country`, `metric` (alias `story`),
  `player` (player-team-season id), `opponent`, `teams` (comma-separated club names for
  `matchup`) and `utm_campaign`. Returns `{spec, season, fetched_at, stale, warning, link}`;
  `400` for an unknown kind/metric, `502` when the site is down.
- `POST /api/growth/cards/preview/` — body `{spec}` or any `suggest` parameter set plus
  `format` (`x`, `instagram`, `story`, `reddit`, `og`). Returns `image/png` (1600×900 by
  default). Nothing is stored.
- `POST /api/growth/captions/` — body `{spec | kind…, link?, utm_campaign?, platforms?,
  locales?}`. Returns `{spec, link, drafts[]}`; each draft carries `platform`, `locale`,
  `title` (Reddit only), `text`, `hashtags`, `length`, `limit`, `within_limit` and
  `localisation` (`full` for EN/EL, `hook` for TR/SR/LT). Without an explicit `link`, each
  platform gets its own UTM URL except Reddit, which is deliberately left without one.
- `POST /api/growth/plan/` — body `{campaign, start_date?, round_label?, season?, country?,
  briefs?}`. `start_date` snaps back to its Monday. Creates one `ContentItem` per slot (8)
  plus a matching `Task`; idempotent, so re-running reports `skipped`. Returns `{created,
  skipped, tasks, week_start, missing_channels, items, warning}`.
- `GET/POST /api/cards/` — the saved-card library. `POST` body `{spec | kind…, format?,
  campaign?}` renders and stores the PNG in the media library together with the exact
  numbers. `DELETE /api/cards/{id}/` removes the record; the file stays on disk.
- `POST /api/cards/{id}/recaption/` — body `{link?, platforms?, locales?}`; re-uses the
  stored spec to produce new copy.
- `GET /api/growth/report/` — `?days=1..365` (default 30) and `?campaign=`. Returns `totals`
  and `previous_totals` (posts, impressions, engagements, comments, clicks,
  `engagement_rate`, `click_rate`), `by_platform` (same shape plus `best_post`) ranked by
  click rate, `by_kind` and `by_metric` breakdowns, `trend` (per-platform change against the
  equally long window before), `traffic` (the GA4 summary below), `traffic_configured` and
  the top five `best_posts`.
- `GET /api/growth/insights/` — `?days=1..365` (default 30) and `?campaign=`. The report
  aggregated into `insights[]` (`severity`, `title`, `detail`, `evidence[]`, optional
  `action`) and `next_cards[]` (`kind`, `metric`, `country`, `reason`) ready to drop into the
  studio form. Rules cover best platform/card type/metric by click rate, clicks that never
  produced GA4 sessions, GA4 traffic from an unlogged channel, reach without conversion,
  falling behind the cadence and stale experiments. Problems (`warn`) sort first, then wins,
  then housekeeping.
- `GET /api/growth/traffic/` — `?days=1..365` (default 30) and `?source=`. Stored GA4
  snapshots plus a `summary` (`totals`, `by_platform`, `by_source`), `configured`,
  `can_sync` and `last_synced_at`. Reads the database only; never calls Google.
- `POST /api/growth/traffic/sync/` — body `{days?}` (default 30). Pulls per-day sessions per
  source from the GA4 Data API into `TrafficSnapshot` rows (idempotent per date/source/medium)
  and returns `{created, updated, rows, sessions, social_sessions, other_sources, start,
  end, last_synced_at}`. Staff only; `400` when GA4 is not configured, `502` when Google
  refuses the call.
- `/api/performance/` — CRUD for published-post numbers, including `kind`, `metric_key`, and
  the derived `click_rate`/`engagement_rate`. `/api/experiments/` — CRUD for growth
  experiments (`name`, `hypothesis`, `metric`, `status`, `result`, dates).

GA4 sessions per source are imported with `python manage.py sync_google --organic` (revenue
sync plus organic; `--days` defaults to 7 for revenue and 30 for traffic).

## Backup & restore

Settings → **Backup & restore** covers exporting and replacing data.

- `GET /api/backup/export/` — any authenticated user. Streams a JSON file (`marketing-backup-YYYY-MM-DD.json`) with every business model: `channels`, `campaigns`, `content`, `ads`, `results`, `plans`, `suggestions`, `shop`, saved `cards`, `performance`, `experiments` and GA4 `traffic` snapshots. Users, passwords and stored API keys are **never** included; `Campaign.owner` is written as a username.
- `GET /api/backup/database/` — any authenticated user, SQLite only (400 otherwise). Streams a consistent snapshot of the whole `db.sqlite3`, accounts included.
- `POST /api/backup/restore/` — staff only. Multipart `file` plus `confirm=replace`. A JSON backup replaces all business data (accounts and API keys are kept); a `.sqlite3` file replaces the whole database after keeping a timestamped `.bak` copy next to it (restart the server afterwards). Unknown files → 400.

## Ops

- `GET /api/health/` — DB-checked health (503 when the database is unreachable).
- `GET /api/config/` — public runtime flags: `{"registration_enabled": bool, "users_exist": bool}`.
