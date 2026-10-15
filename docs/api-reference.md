# API reference

Base `/api/`. Auth: `POST /api/token/`, `POST /api/token/refresh/`, `POST /api/register/` (username + password min 4 chars via `DJANGO_PASSWORD_MIN_LENGTH`, returns JWT pair).

- `GET/POST /api/campaigns/`, `/api/channels/`, `/api/content/`, `/api/spend/`, `/api/metrics/`, `/api/tasks/`, `/api/suggestions/`, `/api/products/`, `/api/orders/`
- `POST /api/metrics/import-csv/` file field `file`, columns `campaign,date,revenue,orders,spend,ctr,roas`
- `POST /api/spend/import-csv/` columns `campaign,channel,date,spend,impressions,clicks,conversions`
- `POST /api/suggestions/generate/` body `{"campaign": id}` → rule suggestions
- `POST /api/suggestions/generate-ai/` body `{"campaign": id, "api_key?": "..."}` → 501 without key, else stored kind=ai
- `GET /api/dashboard/summary/` totals + per-campaign ROAS
- `GET /api/health/`
