# Frontend (React + Vite)

Dark enterprise monitoring dashboard built with React, React Router, Tailwind CSS v4, Recharts and Lucide.
The browser talks only to the FastAPI backend (Vite proxies `/api` to `http://localhost:8000` in
development); it never reaches MySQL.

```bash
npm install
npm run dev      # http://localhost:5173  (start the backend first)
npm run lint
npm run build
```

Optional environment variables: `VITE_API_BASE_URL` (default `/api`) and `VITE_SIMULATED_DATA=false` to hide
the "Simulated demo data" badge.

## Pages

| Route | Page | Access |
|---|---|---|
| `/login` | Sign in | public |
| `/dashboard` | KPIs, activity chart, top destinations, node activity, recent events, system health (auto-refreshes every 15 s) | signed in |
| `/nodes`, `/nodes/:id` | Node list and detail; add / edit / disable | read: all, write: admin |
| `/devices`, `/devices/:id` | Device list and investigation page | signed in |
| `/destinations`, `/destinations/:id` | Destination list and investigation page | signed in |
| `/history` | Search and filter events (URL-synced), event detail panel | signed in |
| `/reports` | Top destinations, top devices, node activity, activity over time (24h / 7d / 30d / custom) | signed in |
| `/users` | User management | admin |
| `/settings` | Account, system status, about | signed in |

## Structure

- `src/services/` — `api.js` (the only place that calls `fetch`: bearer token, error normalisation, 401
  handling) plus one module per API area (`nodes.js`, `history.js`, ...).
- `src/hooks/` — `useAsync` (loading / error / data, abort, polling), `useUrlState`, `useDebounce`, auth.
- `src/components/ui/` — cards, badges, tables, fields, modals, pagination, and the shared loading /
  empty / error states (`DataState`).
- `src/components/charts/` — Recharts wrappers with a shared dark theme.
- `src/pages/`, `src/routes/`, `src/layouts/` — pages (lazy-loaded), route guards, app shell.

## Notes

- The session token is kept in `localStorage` so a refresh keeps you signed in. Tokens are short-lived and the
  backend re-checks every request; the frontend route guards are only a convenience, not the security boundary.
- The login page lists the seeded demo accounts in development builds only.
