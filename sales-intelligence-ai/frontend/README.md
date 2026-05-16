# Frontend — Sales Intelligence AI

React 18 + Vite + TypeScript + Tailwind. RTL-first, Hebrew + English.

## Run

```
npm install
npm run dev
```

Opens at http://localhost:5173. Vite proxies `/api/*` to `http://localhost:8000`,
so start the backend first.

## Pages

- `/` — Dashboard (KPIs, alerts, top items, store ranking)
- `/imports` — Run import on folder, see import logs, upload a file
- `/chat` — Hebrew/English AI chat
- `/reports` — Generate JPG / PNG / PDF reports and download them

## Build

```
npm run build
```

Outputs static assets in `dist/`. Serve behind nginx (see `docs/deployment.md`).
