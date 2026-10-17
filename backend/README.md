# Backend — Social Media Manager

Django + DRF + SimpleJWT. ORM only, no raw SQL.

## Setup

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
.\.venv\Scripts\python.exe backend\manage.py migrate
.\.venv\Scripts\python.exe backend\manage.py createsuperuser
.\.venv\Scripts\python.exe backend\manage.py runserver
```

Env: copy `.env.example` to `.env`. `OPENAI_API_KEY` optional (AI suggestions) — it can also be saved from the app's Settings → API keys (encrypted at rest, DB-first with env fallback; the `cryptography` requirement powers that). GA4 sync is optional too: `GOOGLE_ANALYTICS_CREDENTIALS` (service-account JSON) + `GOOGLE_ANALYTICS_PROPERTY_ID`, or save both in Settings → API keys, then `manage.py sync_google`. Postgres: set `DATABASE_URL=postgres://user:pass@host:5432/dbname` (parsed by `dj-database-url`, installed via requirements); SQLite is the fallback.

## Checks

```powershell
.\.venv\Scripts\python.exe backend\manage.py check

# Bare `test` discovers nothing when run from the repo root; pass app labels:
.\.venv\Scripts\python.exe backend\manage.py test campaigns results ads google_sync -v 1

# Or run from inside backend/ to execute everything:
cd backend
..\.venv\Scripts\python.exe manage.py test
```

`backend/.env` is read at startup (`DJANGO_*`, `OPENAI_API_KEY`, `JWT_*`). Keys saved via Settings → API keys live (encrypted) in the database and take precedence over these env vars — see `docs/api-keys.md`.
Registration is open until the first account exists (that account becomes the admin); afterwards it stays closed unless `DJANGO_ALLOW_REGISTRATION=True`. Accounts are username + password only.
