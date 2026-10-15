# API reference

Base `/api/`. Auth: `POST /api/token/`, `POST /api/token/refresh/`, `POST /api/register/` (disabled by default — enable with `DJANGO_ALLOW_REGISTRATION=True`; username + password, min length via `DJANGO_PASSWORD_MIN_LENGTH`, returns JWT pair).

- `GET/POST /api/campaigns/`, `/api/channels/`, `/api/content/`, `/api/spend/`, `/api/metrics/`, `/api/tasks/`, `/api/suggestions/`, `/api/products/`, `/api/orders/`
- `POST /api/metrics/import-csv/` file field `file`, columns `campaign,date,revenue,orders,spend,ctr,roas` (roas derived from revenue/spend when omitted)
- `POST /api/spend/import-csv/` columns `campaign,channel,date,spend,impressions,clicks,conversions`
  - Both import endpoints return `{created, updated, error_count, errors: [{row, error}]}`; invalid rows are skipped and reported with their CSV line number.
- `POST /api/suggestions/generate/` body `{"campaign": id}` → rule suggestions
- `POST /api/suggestions/generate-ai/` body `{"campaign": id, "api_key?": "..."}` → 501 without key, else stored kind=ai
- `GET /api/dashboard/summary/` totals + per-campaign ROAS
- `GET /api/health/` DB-checked health, `GET /api/config/` public runtime flags
