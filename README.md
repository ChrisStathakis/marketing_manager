# Social Media Manager

Manage social/ads campaigns for your basket shop: plan content, track spend + results, get next-step suggestions.

## Layout

- `backend/` — Django 5 + DRF + SimpleJWT (SQLite dev, Postgres-ready). Apps: `campaigns channels content ads results plans suggestions shop growth`.
- `frontend/` — Vite + React 19 + TS + React Router + TanStack Query + Zustand + Recharts.
- `docs/` — the documentation site: a user guide for the people running campaigns, plus setup, architecture and API reference.

## Quickstart

Backend (Windows, system Python 3.12):

```powershell
cd marketing
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
copy backend\.env.example backend\.env
.\.venv\Scripts\python.exe backend\manage.py migrate
.\.venv\Scripts\python.exe backend\manage.py createsuperuser
.\.venv\Scripts\python.exe backend\manage.py runserver
```

Frontend:

```cmd
cd frontend
copy .env.example .env
npm install
npm run dev
```

Open `http://localhost:5173`, login with the Django superuser. API at `http://127.0.0.1:8000/api/`.

## Key endpoints

See `docs/api-reference.md` for the full list (pagination, filters, CSV).

- `POST /api/token/` login, `/api/campaigns/`, `/api/metrics/` + `/import-csv/` + `/export-csv/`, `/api/spend/` + `/import-csv/` + `/export-csv/`
- `POST /api/suggestions/generate/` rules (always works), `POST /api/suggestions/generate-ai/` needs an OpenAI key (Settings → API keys, or `OPENAI_API_KEY`), `POST /api/suggestions/{id}/accept/` turns one into a task
- `GET /api/dashboard/summary/` (`?days=30` or `?date__gte/date__lte`), `GET /api/health/`, `GET /api/config/`
- `GET/PUT/DELETE /api/integrations/` manage third-party credentials from the UI (write-only, encrypted at rest) — see `docs/api-keys.md`
- `POST /api/integrations/google-analytics/sync/` (or `manage.py sync_google --days 7`) imports GA4 revenue/orders per campaign into daily metrics, so results don't have to be imported as CSV
- `GET /api/backup/export/` (JSON business data), `GET /api/backup/database/` (whole SQLite file), `POST /api/backup/restore/` (staff; replaces everything from a JSON or `.sqlite3` backup) — see Settings → Backup & restore
- **Growth studio** (`/growth`): `GET /api/growth/suggest/` picks a card from the public catchandstats.com season data, `POST /api/growth/cards/preview/` renders a PNG (Pillow — X/Instagram/story/Reddit/OG sizes), `POST /api/growth/captions/` drafts copy in EN/EL/TR/SR/LT, `POST /api/growth/plan/` fills next week's calendar and to-dos, `GET /api/growth/report/` summarises logged post performance (by platform, card type, metric, with a window-over-window trend), `GET /api/growth/insights/` turns that into rule-based next actions, and `GET/POST /api/growth/traffic/` (`…/traffic/sync/`) reads GA4 sessions per source so clicks can be checked against visits. Read-only against the site: nothing is published automatically.
- **Instagram comment research** (`/growth`, section 8): `GET/POST /api/growth/instagram/posts/`, `POST /api/growth/instagram/posts/{id}/scrape/` (staff), `GET /api/growth/instagram/comments/`, `GET /api/growth/instagram/analysis/`, `GET /api/growth/instagram/export/` (CSV) and `POST /api/growth/instagram/test/` (staff) collect the **commenters** on a public post using a logged-in `sessionid` cookie (Settings → API keys → Instagram, or `INSTAGRAM_SESSIONID`), or `manage.py instagram_check`. Not official API usage and likers are not available; turn it off with `INSTAGRAM_SCRAPER_ENABLED=False`. See `docs/api-keys.md`.

## Tests

```powershell
# From backend/ this runs the whole suite:
cd backend
..\.venv\Scripts\python.exe manage.py test
```

Frontend checks (type-check, lint, build) run the same way CI does: `cd frontend; npx tsc -p tsconfig.app.json --noEmit; npm run lint; npm run build`.

## Docs

The documentation site is built with [MkDocs Material](https://squidfunk.github.io/mkdocs-material/)
from `docs/` (`mkdocs.yml` at the root). It has two parts: a **User guide** written for the people
who run campaigns, and **For developers** (setup, architecture, API reference, API keys).

```powershell
python -m pip install -r requirements-docs.txt
mkdocs serve -a 127.0.0.1:8080   # preview — 8000 is Django's port
mkdocs build --strict            # static site into site/ (gitignored)
```

CI runs `mkdocs build --strict` on every push, so a broken link or a missing image fails the
build instead of shipping. Screenshots are regenerated with the tool in `tools/screenshots/`
(see its README).

## CI

`.github/workflows/ci.yml` runs the backend suite (SQLite), the frontend type-check + lint + build, and the docs build on every push and PR.

## Notes

- Registration is open until the first account exists (that account becomes the admin); afterwards it is closed and only reopens with `DJANGO_ALLOW_REGISTRATION=True` in `backend\.env`. Accounts are username + password only — no email, no password length rules.
- Postgres: set `DATABASE_URL=postgres://user:pass@host:5432/dbname` in `backend\.env` (parsed with `dj-database-url`; SQLite is the fallback).
- Google Analytics 4 sync (optional): add a service-account JSON + GA4 property ID in Settings → API keys (or `GOOGLE_ANALYTICS_CREDENTIALS` / `GOOGLE_ANALYTICS_PROPERTY_ID`), then Sync now. Rows that match no `utm_campaign` are reported instead of dropped. See `docs/api-keys.md`.
- Result rows record where they came from (`source`: `manual` / `ga4` / `google_ads`); a CSV import always marks rows `manual`, and a GA4 sync only writes revenue/orders — never spend.
- AI suggestions run server-side only; never put API keys in `VITE_*` vars. Manage them in Settings → API keys (encrypted in the app database) or in `backend\.env` — both stay server-side.
- Growth studio reads the public `catchandstats.com` API read-only and caches each season under `backend/media/growth-cache/` for six hours. Override with `CATCHANDSTATS_API_BASE`, `CATCHANDSTATS_SITE_URL`, `CATCHANDSTATS_TIMEOUT`, `GROWTH_CACHE_TTL_HOURS` and `GROWTH_CACHE_DIR`. Card rendering needs `Pillow` (installed from `backend/requirements.txt`); in production serve `backend/media/` yourself, since Django only serves it in `DEBUG`. The traffic panel reuses the `google-analytics` integration and can also be filled by `python manage.py sync_google --organic`.
- Instagram comment research (optional) uses a logged-in `sessionid` cookie — **not official API usage**, and likers are unavailable. `curl_cffi` (in `backend/requirements.txt`) is required. `INSTAGRAM_MAX_COMMENTS`, `INSTAGRAM_TIMEOUT` and `INSTAGRAM_PROXY` tune it; `INSTAGRAM_SCRAPER_ENABLED=False` turns it off. See `docs/api-keys.md`.
- Demo data: from `backend\`, run `..\.venv\Scripts\python.exe manage.py seed_demo` to fill the app with sample campaigns, content, metrics and orders (add `--reset` to rebuild). Users and saved API keys are never touched.
