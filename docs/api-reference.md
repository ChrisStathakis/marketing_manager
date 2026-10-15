# API reference

Base `/api/`. Auth: `POST /api/token/`, `POST /api/token/refresh/`, `POST /api/register/` (disabled by default — enable with `DJANGO_ALLOW_REGISTRATION=True`; username + password, min length via `DJANGO_PASSWORD_MIN_LENGTH`, returns JWT pair). Authenticated calls use `Authorization: Bearer <access>`.

## Resources

Full CRUD (`GET`, `POST`, `PATCH`, `PUT`, `DELETE` on detail routes):

- `/api/campaigns/`, `/api/channels/`, `/api/content/`, `/api/spend/`, `/api/metrics/`, `/api/tasks/`, `/api/suggestions/`, `/api/products/`, `/api/orders/`

## Pagination, search and filters

Every list endpoint is paginated: `?page=`, `?page_size=` (default 20, max 500). Responses use the DRF envelope `{count, next, previous, results}`.

| Resource | Search | Ordering | Filters |
| --- | --- | --- | --- |
| campaigns | `name objective utm_campaign` | `created_at start_date budget name` | `status`, `owner` |
| channels | `name handle` | `name` | `channel_type`, `is_active` |
| content | `title copy` | `publish_at id` | `campaign`, `channel`, `status`, `publish_at__gte`, `publish_at__lte` (ISO datetime) |
| tasks | `title notes` | `due_date created_at` | `campaign`, `done`, `suggestion`, `due_date__gte`, `due_date__lte` |
| metrics | — | `date revenue spend` | `campaign`, `date`, `date__gte`, `date__lte` |
| spend | — | `date spend` | `campaign`, `channel`, `date`, `date__gte`, `date__lte` |
| suggestions | — | `created_at` | `campaign`, `kind`, `accepted` |
| products | `name external_id` | `name updated_at` | — |
| orders | — | `ordered_at total` | `campaign`, `utm_source`, `utm_campaign` |

Range filters power the calendar (`content?publish_at__gte=…&publish_at__lte=…`) and reporting (`metrics?date__gte=…&date__lte=…`).

## CSV import / export

- `POST /api/metrics/import-csv/` — file field `file`, columns `campaign,date,revenue,orders,spend,ctr,roas` (roas derived from revenue/spend when omitted).
- `POST /api/spend/import-csv/` — columns `campaign,channel,date,spend,impressions,clicks,conversions`.
- Both import endpoints return `{created, updated, error_count, errors: [{row, error}]}`; invalid rows are skipped and reported with their CSV line number.
- `GET /api/metrics/export-csv/` and `GET /api/spend/export-csv/` — stream an import-compatible CSV honouring every list filter above (`campaign`, date ranges, channel…). A null channel exports as an empty value.

## Suggestions

- `POST /api/suggestions/generate/` body `{"campaign": id}` → rule suggestions. Re-running refreshes open suggestions with the same title instead of stacking duplicates.
- `POST /api/suggestions/generate-ai/` body `{"campaign": id, "api_key?": "..."}` → 501 without key, else stored/refreshed as kind=ai.
- `POST /api/suggestions/{id}/accept/` body `{"title?", "due_date?"}` → marks accepted and creates a linked task (idempotent: returns the existing task with `created: false` on repeat).
- `POST /api/suggestions/{id}/reopen/` → moves it back to the open list; any created task is kept.
- The serializer includes the linked `task {id, title, done, due_date}` or `null`.

## Dashboard

`GET /api/dashboard/summary/` — totals (`spend`, `revenue`, `orders`, `roas`), `deltas` vs the previous same-length window (percent, `null` when there is no basis), a daily `series` of revenue/spend/orders, the resolved `range`, and the top-20 `campaigns` breakdown.

- `?days=N` — last N days ending today, e.g. `?days=30`.
- `?date__gte=YYYY-MM-DD&date__lte=YYYY-MM-DD` — explicit range (overrides `days` when `date__gte` is given).
- No params → all time (deltas are `null`).

## Ops

- `GET /api/health/` — DB-checked health (503 when the database is unreachable).
- `GET /api/config/` — public runtime flags: `{"registration_enabled": bool}`.
