# Frontend — Social Media Manager

Vite + React + TS + Router + TanStack Query + Zustand + Recharts. UI: Tailwind v4 with CSS-first design tokens (dark mode included) and a local shadcn-style component library in `src/ui/` (Radix + cva + lucide + sonner); forms use react-hook-form + zod.

```cmd
copy .env.example .env
npm install
npm run dev
npm run build
npm run lint
```

Checks used by CI: `npx tsc -p tsconfig.app.json --noEmit`, `npm run lint`, `npm run build`.

`VITE_API_URL` defaults to `/api` (vite proxy to `127.0.0.1:8000` in dev).

## Design system ("agro")

The visual language is ported from the AgroEcosystem app (`cell_phone/` React app + its Django web UI): forest/pine greens, cream surfaces, gold accents, sage washes, Inter type, 20px card / 14px field radii, pill buttons, soft shadows.

- **Tokens** live in `src/index.css`. Raw palette variables (`--pine`, `--gold`, `--sage`, cards, lines, status tones, sidebar/topbar, chart colors) are defined for light in `:root` and for dark in `.dark`, then mapped through `@theme inline` into Tailwind utilities (`bg-pine`, `text-gold`, `rounded-card`, `shadow-soft`, …). Change colors there, never in components.
- **Font**: Inter Variable via `@fontsource-variable/inter` (self-hosted, offline-safe).
- **Primitives** (`src/ui/`): buttons are pills with a press scale, inputs get a green focus glow, cards lift on hover where interactive, skeletons pulse, dialogs/dropdowns open with a small pop.
- **Motion**: `enter` (route fade-up) and `enter-stagger` utilities; all transitions/animations are disabled under `prefers-reduced-motion`.

Keep new components on the token utilities so light/dark and future palette changes stay automatic.
