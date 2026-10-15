# Architecture

- Backend apps with thin ViewSets: campaigns, channels, content, ads, results, plans, suggestions, shop.
- Business logic in `suggestions/services.py` (snapshot + rules + LLM call). ORM only.
- Auth: SimpleJWT; DRF defaults: IsAuthenticated, pagination 20, filter/search/ordering.
- Frontend features map 1:1 to API: dashboard, campaigns, calendar, results (CSV), suggestions, settings (UTM builder).
