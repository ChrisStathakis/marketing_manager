# Setup

See root README. Backend: venv + `pip install -r backend/requirements.txt` + `migrate` + `createsuperuser` + `runserver`. Frontend: `npm install` + `npm run dev`. Login uses Django JWT.

On a fresh install, `createsuperuser` is optional: the first person to use **Create account** on the login screen becomes the admin (registration closes afterwards). Accounts are username + password only — no email.

API keys (optional, e.g. OpenAI for AI suggestions, a GA4 service account to import results, or a Search Console service account for assisted search data): save them in Settings → API keys after login, or set env vars in `backend/.env` — see [api-keys.md](api-keys.md).

Demo data: from `backend/` run `manage.py seed_demo` (add `--reset` to rebuild) — sample campaigns, content, metrics and orders for exploring the UI. For the assisted-search section without Google credentials, run `manage.py seed_search_console --days 30`.

Top 8 playbook: from `backend/` run `manage.py seed_playbook` once (add `--force` to refresh the seeded slots). It creates the editable 14-day series under **Playbooks**, plus the Greek/English/Turkish/Serbian/Lithuanian hashtag banks.
