# Setup

See root README. Backend: venv + `pip install -r backend/requirements.txt` + `migrate` + `createsuperuser` + `runserver`. Frontend: `npm install` + `npm run dev`. Login uses Django JWT.

On a fresh install, `createsuperuser` is optional: the first person to use **Create account** on the login screen becomes the admin (registration closes afterwards). Accounts are username + password only — no email.

API keys (optional, e.g. OpenAI for AI suggestions, or a GA4 service account to import results): save them in Settings → API keys after login, or set env vars in `backend/.env` — see [api-keys.md](api-keys.md).

Demo data: from `backend/` run `manage.py seed_demo` (add `--reset` to rebuild) — sample campaigns, content, metrics and orders for exploring the UI.
