# Frontend — Basket Campaign Manager

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
