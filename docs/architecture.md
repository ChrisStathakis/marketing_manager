# Architecture

- Backend apps with thin ViewSets: campaigns, channels, content, ads, results, plans, suggestions, shop.
- Business logic in `suggestions/services.py` (snapshot + rules + LLM call). ORM only.
- Auth: SimpleJWT; DRF defaults: IsAuthenticated, pagination 20, filter/search/ordering.
- Frontend features map 1:1 to API: dashboard, campaigns, calendar, results (CSV), suggestions, settings (UTM builder).
- Frontend design system ("agro", ported from the AgroEcosystem react app): CSS-first tokens in `frontend/src/index.css` (palette, radii, shadows, motion) mapped into Tailwind utilities via `@theme inline`; primitives in `frontend/src/ui/`. Palette/mode changes belong in tokens, not components. See `frontend/README.md`.
