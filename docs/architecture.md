# Architecture

- Backend apps with thin ViewSets: campaigns, channels, content, ads, results, plans, suggestions, shop.
- Business logic in `suggestions/services.py` (snapshot + rules + LLM call). ORM only.
- `google_sync` owns the outbound Google integrations: `ga4.py` (service-account JWT + GA4 Data API over REST/urllib), `mapping.py` (`sessionCampaignName` → `Campaign.utm_campaign`), `services.py` (idempotent upsert into `results.DailyMetric`), a `sync_google` command and a staff-only sync endpoint. Credentials/settings come from `integrations`.
- Auth: SimpleJWT; DRF defaults: IsAuthenticated, pagination 20, filter/search/ordering.
- Frontend features map 1:1 to API: dashboard, campaigns, calendar, results (CSV), suggestions, settings (UTM builder).
- Frontend design system ("agro", ported from the AgroEcosystem react app): CSS-first tokens in `frontend/src/index.css` (palette, radii, shadows, motion) mapped into Tailwind utilities via `@theme inline`; primitives in `frontend/src/ui/`. Palette/mode changes belong in tokens, not components. See `frontend/README.md`.
