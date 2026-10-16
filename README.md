# Social Media Manager

Manage social/ads campaigns for your basket shop: plan content, track spend + results, get next-step suggestions.

## Layout

- `backend/` — Django 5 + DRF + SimpleJWT (SQLite dev, Postgres-ready). Apps: `campaigns channels content ads results plans suggestions shop`.
- `frontend/` — Vite + React 19 + TS + React Router + TanStack Query + Zustand + Recharts.
- `docs/` — setup, architecture, API reference.

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
- `GET/PUT/DELETE /api/integrations/` manage third-party keys from the UI (write-only, encrypted at rest) — see `docs/api-keys.md`

## Tests

```powershell
# From backend/ this runs the whole suite:
cd backend
..\.venv\Scripts\python.exe manage.py test
```

Frontend checks (type-check, lint, build) run the same way CI does: `cd frontend; npx tsc -p tsconfig.app.json --noEmit; npm run lint; npm run build`.

## CI

`.github/workflows/ci.yml` runs the backend suite (SQLite) and the frontend type-check + lint + build on every push and PR.

## Notes

- Public registration is disabled by default (single-admin app). Set `DJANGO_ALLOW_REGISTRATION=True` in `backend\.env` to allow `/api/register/`.
- Postgres: set `DATABASE_URL=postgres://user:pass@host:5432/dbname` in `backend\.env` (parsed with `dj-database-url`; SQLite is the fallback).
- AI suggestions run server-side only; never put API keys in `VITE_*` vars. Manage them in Settings → API keys (encrypted in the app database) or in `backend\.env` — both stay server-side.
- Demo data: from `backend\`, run `..\.venv\Scripts\python.exe manage.py seed_demo` to fill the app with sample campaigns, content, metrics and orders (add `--reset` to rebuild). Users and saved API keys are never touched.
