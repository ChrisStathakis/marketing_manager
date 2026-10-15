# Basket Campaign Manager

Manage social/ads campaigns for your basket shop: plan content, track spend + results, get next-step suggestions.

## Layout

- `backend/` — Django 5 + DRF + SimpleJWT (SQLite dev, Postgres-ready). Apps: `campaigns channels content ads results plans suggestions shop`.
- `frontend/` — Vite + React 19 + TS + React Router + TanStack Query + Zustand + Recharts.
- `docs/` — setup, architecture, API reference.

## Quickstart

Backend (Windows, system Python 3.12):

```powershell
cd basket-campaign-manager
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

- `POST /api/token/` login, `/api/campaigns/`, `/api/metrics/` + `/import-csv/`, `/api/spend/` + `/import-csv/`
- `POST /api/suggestions/generate/` rules (always works), `POST /api/suggestions/generate-ai/` needs `OPENAI_API_KEY`
- `GET /api/dashboard/summary/`, `GET /api/health/`, `GET /api/config/`

## Tests

```powershell
# From the repo root (app labels required):
.\.venv\Scripts\python.exe backend\manage.py test campaigns results ads
```

## Notes

- Public registration is disabled by default (single-admin app). Set `DJANGO_ALLOW_REGISTRATION=True` in `backend\.env` to allow `/api/register/`.
- Frontend chunk >500kB warning is Recharts; code-split later if needed.
- Tailwind was skipped after an npm registry SSL failure; UI uses modern plain CSS. Add Tailwind v4 (`tailwindcss @tailwindcss/vite`) when network allows.
- AI suggestions run server-side only; never put API keys in `VITE_*` vars.
