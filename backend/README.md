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
.\.venv\Scripts\python.exe backend\manage.py test campaigns -v 2
```
