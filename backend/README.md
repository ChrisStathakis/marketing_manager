# Backend — Basket Campaign Manager

Django + DRF + SimpleJWT. ORM only, no raw SQL.

## Setup

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
.\.venv\Scripts\python.exe backend\manage.py migrate
.\.venv\Scripts\python.exe backend\manage.py createsuperuser
.\.venv\Scripts\python.exe backend\manage.py runserver
```

Env: copy `.env.example` to `.env`. `OPENAI_API_KEY` optional (AI suggestions). `DATABASE_URL` documented for Postgres (requires `dj-database-url`, not installed).

## Checks

```powershell
.\.venv\Scripts\python.exe backend\manage.py check

# Bare `test` discovers nothing when run from the repo root; pass app labels:
.\.venv\Scripts\python.exe backend\manage.py test campaigns results ads -v 1

# Or run from inside backend/ to execute everything:
cd backend
..\.venv\Scripts\python.exe manage.py test
```

`backend/.env` is read at startup (`DJANGO_*`, `OPENAI_API_KEY`, `JWT_*`).
Registration is disabled unless `DJANGO_ALLOW_REGISTRATION=True`.
