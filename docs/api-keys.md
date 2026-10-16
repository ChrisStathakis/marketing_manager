# API keys

Third-party keys the backend can use. They are managed in **Settings → API keys** or via
`backend/.env`; the app works without any of them (the related feature just stays off).

## How keys are handled

- **Precedence:** an explicit `api_key` in a request body → a key saved in Settings (database)
  → the environment variable from `backend/.env`.
- **Storage:** saved keys are encrypted at rest (Fernet, key derived from `DJANGO_SECRET_KEY`)
  in the `IntegrationCredential` table. The API returns configuration status only — never the value.
- **Write-only:** once saved, a key can be replaced or removed, but it is never displayed again.
  A last-4-characters hint is kept so you can tell which key is active.
- **Permissions:** only staff users (`is_staff`) can set or remove keys; any signed-in user can
  read the status list.
- **Rotation caveat:** rotating `DJANGO_SECRET_KEY` makes saved keys unreadable. The Settings card
  flags them as *Needs attention* — remove the entry and save the key again.

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

## API

See `docs/api-reference.md` → Integrations.
