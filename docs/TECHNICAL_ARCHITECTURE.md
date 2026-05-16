# Technical Architecture

_Generated: 2026-05-03 — point-in-time snapshot._

## Stack

### Backend

| Layer | Choice | Version (per `requirements.txt`) |
| --- | --- | --- |
| Web framework | FastAPI | ≥ 0.118.0 |
| ASGI server | uvicorn[standard] | ≥ 0.34.0 |
| ORM | SQLAlchemy 2 | ≥ 2.0.40 |
| Schemas / validation | Pydantic v2 | ≥ 2.11.0 |
| Schema migrations | Alembic configured + custom additive `add_missing_columns` | — |
| Background jobs | APScheduler | ≥ 3.11.0 |
| File uploads | python-multipart | ≥ 0.0.20 |
| Excel I/O | openpyxl | ≥ 3.1.5 |
| Legacy `.xls` support | xlrd 1.2.0 | (pinned) |
| Date parsing | python-dateutil | ≥ 2.9.0 |
| Email validation | email-validator | ≥ 2.2.0 |
| Password hashing | bcrypt directly (not passlib's bcrypt backend) | (passlib bundled) |
| JWT | python-jose[cryptography] | ≥ 3.3.0 |
| Gmail API | google-auth + google-api-python-client | latest |
| PDF text extraction | pypdf | ≥ 6.0.0 |
| Database (dev) | SQLite, file at `backend/data/royal_linen.db` | — |
| Database (prod-ready) | Postgres via env `DATABASE_URL` | — |

### Frontend

| Layer | Choice | Version (per `package.json`) |
| --- | --- | --- |
| Framework | React | ^18.3.1 |
| Build tool | Vite | ^5.4.8 |
| Language | TypeScript | ^5.6.2 |
| Routing | react-router-dom | ^6.27.0 |
| Data fetching | @tanstack/react-query | ^5.59.0 |
| HTTP client | axios | ^1.7.7 |
| Auth store | zustand | ^5.0.0 |
| Styling | Tailwind CSS | ^3.4.13 |
| Date util | date-fns | ^4.1.0 |
| Class merging | clsx | ^2.1.1 |

PWA: manifest + service worker + offline fallback page (`offline.html`).

---

## Backend layout

```
backend/app/
├── main.py             ← app factory, scheduler bootstrap, route registration
├── config.py           ← env-var-driven config (DATABASE_URL, AUTH_SECRET, ...)
├── database.py         ← SQLAlchemy engine + SessionLocal + Base
├── seed.py             ← optional seed data (demo)
│
├── models/             ← SQLAlchemy ORM (one model per file or grouped)
│   ├── shipment.py             — Shipment (80 columns)
│   ├── container.py            — Container (45 columns)
│   ├── email_update.py         — EmailUpdate + EmailAttachment
│   ├── pending_shipment.py     — PendingShipment + PendingContainer
│   ├── pending_document_update.py
│   ├── extra_work.py
│   ├── event.py                — ShipmentEvent (audit log)
│   ├── alert.py
│   ├── document_qc.py          — 3 QC tables
│   ├── import_batch.py
│   └── user.py
│
├── routers/            ← 21 FastAPI routers (one router file per area)
│   ├── auth.py            /auth/*
│   ├── users.py           /users/*
│   ├── shipments.py       /shipments/*
│   ├── containers.py      /containers/*
│   ├── documents.py       /documents/*
│   ├── document_qc.py     /qc/*
│   ├── data_review.py     /data-review/*
│   ├── imports.py         /import/*
│   ├── email_router.py    /email/*
│   ├── gmail.py           /gmail/*
│   ├── pending.py         /pending/*
│   ├── pending_shipments.py /pending-shipments/*
│   ├── extra_work.py      /extra-work/*
│   ├── receiving.py       /receiving/*
│   ├── ai.py              /ai/*
│   ├── alerts.py          /alerts/*
│   ├── dashboard.py       /dashboard/*
│   ├── events.py          /events/*
│   ├── export.py          /export/*
│   └── (root /, /health on main.py)
│
├── services/           ← 30 service modules (business logic)
│   ├── auth_service.py             — bcrypt + JWT + RBAC
│   ├── shipment_service.py         — tracked-fields, event audit, manual_overrides
│   ├── container_service.py
│   ├── document_service.py
│   ├── document_classifier_service.py  — rule-based 15-class classifier
│   ├── document_status_service.py      — smart per-shipment doc-status panel
│   ├── document_qc_service.py          — QC scan + supplier rules
│   ├── excel_format_detector.py        — auto-detect ICL / Eli Line / Royal Linen
│   ├── excel_import_service.py         — Royal Linen template parse + apply
│   ├── external_excel_parsers.py       — ICL + Eli Line parsers
│   ├── external_dedup_service.py       — 0-100 scoring engine, 4 match levels
│   ├── external_import_service.py      — apply path + import_batches + rollback
│   ├── excel_preview_service.py        — read .xlsx preview for UI
│   ├── email_parser_service.py         — extract fields from email body
│   ├── email_apply_service.py          — auto-apply policy + manual_overrides safety
│   ├── email_sync_service.py           — orchestrator
│   ├── gmail_service.py                — Gmail API wrapper
│   ├── pending_shipment_service.py
│   ├── extra_work_service.py
│   ├── receiving_service.py
│   ├── alert_service.py                — alert generators
│   ├── dashboard_service.py            — KPI aggregation
│   ├── forecast_service.py             — 8-week container forecast
│   ├── daily_forecast_service.py       — daily pallet forecast
│   ├── pallet_service.py               — Euro/Industrial pallet calculator
│   ├── category_service.py
│   ├── data_quality_service.py         — per-shipment / per-container quality score
│   ├── pdf_service.py                  — pypdf-based text extraction
│   ├── export_service.py               — Excel export
│   ├── ai_assistant_service.py         — rule-based intent matcher
│   └── event_service.py                — append-only audit writer
│
├── schemas/            ← Pydantic v2 schemas (response/request validation)
│   ├── shipment.py
│   ├── container.py
│   ├── email_update.py
│   ├── pending_shipment.py
│   ├── extra_work.py
│   ├── event.py
│   ├── alert.py
│   └── dashboard.py
│
└── utils/
    └── migrations.py   ← additive-only column migration runner
                          (lightweight alternative to Alembic for fast iteration)
```

### App startup sequence (`main.py:lifespan`)

1. `init_db()`:
   - `Base.metadata.create_all(bind=engine)` — create any new tables.
   - `add_missing_columns(engine)` — additive ALTER for any model column
     missing in the DB. The migration runner now correctly emits
     `DEFAULT 0/false` and a backfill `UPDATE` for boolean columns
     (this fixed an earlier silent-data-hidden bug where
     `archived=NULL` rows were filtered out by `archived == False`).
   - `bootstrap_admin(db)` — create the bootstrap admin if no users
     exist.
   - `seed_builtin_rules(db)` — seed canonical
     `document_assignment_rules` for known suppliers.
2. Start `BackgroundScheduler` (Asia/Jerusalem timezone) with one
   `interval` job:
   - `alert_service.scan_alerts(db)`
   - `email_sync_service.sync_now(db)` — sync stub touches last_sync_at;
     real Gmail sync is `/gmail/sync`.
   - `document_qc_service.run_scan(db)`

   Default interval: `EMAIL_SYNC_INTERVAL_MINUTES=60`.

### Route protection

`main.py` applies `Depends(get_current_user)` as a router-level
dependency on every router except `/auth/*` (public login + me) and
`/gmail/*` (OAuth callback can't carry a Bearer token; PKCE protects
the auth code exchange). Per-route role checks use
`require_permission("action.name")` from inside individual routers.

---

## Frontend layout

```
frontend/src/
├── App.tsx           ← top-level routes
├── main.tsx          ← root render + ReactQueryClient + ErrorBoundary
├── index.css         ← Tailwind + RTL utilities
├── vite-env.d.ts
│
├── api/
│   ├── client.ts     ← axios instance + auth interceptor
│   └── endpoints.ts  ← typed wrappers around every backend endpoint
│
├── auth/
│   ├── store.ts      ← zustand store (token + user)
│   └── ProtectedRoute.tsx  ← redirect to /login if no token, role check
│
├── components/
│   ├── Layout.tsx           ← sidebar + mobile drawer + bottom nav
│   ├── AIAssistant.tsx      ← floating AI panel
│   ├── AIPanel.tsx          ← per-page AI panel
│   ├── ArrivalsTimeline.tsx
│   ├── AuthedImage.tsx      ← <img> via blob URL with auth header
│   ├── DataQuality.tsx
│   ├── DocumentCard.tsx     ← classification badge + reclassify menu
│   ├── ErrorBoundary.tsx
│   ├── ExcelPreview.tsx
│   └── common.tsx
│
├── hooks/            ← (custom hooks)
│
├── pages/            ← 25 page components — see FRONTEND_SCREENS.md
│
├── types/index.ts    ← shared TypeScript types
│
└── utils/
    ├── fileAccess.ts   ← useAuthedFile(url) → Blob URL
    └── format.ts       ← Hebrew dates / numbers
```

---

## Authentication

### Password hashing

`bcrypt` directly (not via passlib's bcrypt backend, because passlib
1.7.4 does not work with the latest bcrypt 5.x).

```python
def hash_password(plain: str) -> str:
    pw = plain.encode("utf-8")[:72]   # bcrypt 72-byte limit
    return bcrypt.hashpw(pw, bcrypt.gensalt(rounds=12)).decode("utf-8")
```

### JWT (HS256)

```python
{ "sub": user_id, "username": ..., "role": ..., "iat": ..., "exp": ... }
```

- Secret: `AUTH_SECRET` env var (dev default rejected by `is_production()`).
- TTL: `AUTH_TOKEN_TTL_HOURS=24` by default.
- The frontend stores the token in `localStorage` and the axios
  interceptor adds `Authorization: Bearer <token>`.
- Stateless logout — `/auth/logout` only confirms the user is
  authenticated; the client deletes the token from `localStorage`.

### RBAC (role-based access control)

Permission matrix lives in
`services/auth_service.py:PERMISSIONS`. Examples:

| Action | Allowed roles |
| --- | --- |
| `shipment.create` / `update` | admin, import_manager |
| `shipment.delete` | admin |
| `shipment.archive` | admin, import_manager |
| `email.approve` / `reject` | admin, import_manager |
| `gmail.connect` | admin |
| `receiving.update` | admin, import_manager, warehouse |
| `document.upload` / `assign` | admin, import_manager, warehouse |
| `users.manage` | admin |
| `shipment.read` / `container.read` / `document.read` / `ai.ask` | all 4 roles |

`require_permission("action.name")` — FastAPI dependency factory.
`/auth/me.permissions` returns the precomputed permission list so the
UI can hide buttons.

### Emergency admin

`EMERGENCY_ADMIN_USERNAME` + `EMERGENCY_ADMIN_PASSWORD` env vars create
a synthetic in-memory admin (id = -1) that can ALWAYS log in, even if
the users table is empty / locked / corrupted. Never persisted.

---

## File storage + authenticated downloads

- All uploaded files live under `backend/uploads/` (configurable via
  `FILE_STORAGE_PATH`).
- `email_attachments.file_path` stores the absolute path on disk.
- The frontend never embeds tokens in URLs. Instead,
  `utils/fileAccess.ts:useAuthedFile(url)` performs an authenticated
  `fetch` and creates a `Blob` URL for the browser to consume. This
  pattern covers PDFs, images, and Excel previews.

---

## Schema migrations

The app uses an **additive-only** custom migration runner
(`backend/app/utils/migrations.py:add_missing_columns`) instead of
Alembic for day-to-day iteration:

- On startup, it inspects each table's `PRAGMA table_info` and adds
  any column declared on the model but missing in the DB.
- For boolean columns, it now correctly emits `DEFAULT 0/false` AND a
  one-shot backfill `UPDATE` so newly-added flags don't surface as
  `NULL` (which silently broke `WHERE archived == False` filters
  earlier).
- It never drops or renames columns. Schema-shape changes that
  require destructive operations would need a real Alembic migration.

Alembic is included in `requirements.txt` and is set up for
production-grade migrations when needed.

---

## Background jobs (APScheduler)

One job, registered at startup, named `hourly_scan`:

```python
def background_jobs():
    db = SessionLocal()
    try:
        alert_service.scan_alerts(db)
        email_sync_service.sync_now(db)
        document_qc_service.run_scan(db)
    finally:
        db.close()
```

Default interval: 60 minutes (env `EMAIL_SYNC_INTERVAL_MINUTES`).
Timezone: `Asia/Jerusalem`.

---

## Frontend data layer

- **TanStack Query** for all reads, with shipment-scoped cache keys
  (e.g. `["shipment-documents", shipmentId]`) so cached data never
  bleeds across shipments.
- **zustand** for auth state (token + user).
- `useSyncExternalStore` is used in places where multiple components
  watch the same auth store; the snapshot is cached at module level
  to avoid React's "getSnapshot returned a different value" infinite
  render loop (this was a previously-fixed blocker).

---

## Health check script

`backend/scripts/check_app_health.py` — pure-stdlib script (no MCP /
browser deps) that performs 8 checks:
1. `GET /health` (backend)
2. `GET /docs`
3. `GET /` (frontend)
4. `GET /login` (frontend)
5. `POST /auth/login` (with bootstrap admin or env-var credentials)
6. `GET /auth/me` (with the JWT)
7. `GET /shipments` (protected)
8. `GET /qc/summary` (protected)

Exit codes: `0` = HEALTHY (8/8 green), `1` = PARTIAL, `2` = DOWN.

The standing operating procedure is: when the UI shows an "API Error"
banner, run this script first. If 8/8 green, the issue is the dev
tool's connection, not the app — keep working.

---

## Logging

Standard Python `logging` configured in `main.py`:
```
%(asctime)s [%(levelname)s] %(name)s: %(message)s
```

Notable loggers:
- `auth` — login attempts, emergency admin use.
- `import` — every external import apply with batch ID + counts.
- `scheduler` — exception trace if QC scan crashes.

---

## Environment variables (full list)

| Variable | Default | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite:///backend/data/royal_linen.db` | DB connection. |
| `AUTH_SECRET` | dev fallback | JWT signing key. **MUST** be overridden in production. |
| `AUTH_TOKEN_TTL_HOURS` | 24 | JWT lifetime. |
| `AUTH_BOOTSTRAP_USERNAME` | `admin` | First-time admin username. |
| `AUTH_BOOTSTRAP_PASSWORD` | `123456` | First-time admin password. Force-change on first login. |
| `EMERGENCY_ADMIN_USERNAME` | (empty) | Break-glass admin. |
| `EMERGENCY_ADMIN_PASSWORD` | (empty) | Break-glass admin. |
| `CORS_ALLOWED_ORIGINS` | `localhost:5173,5174,127.0.0.1:5173` | CSV of allowed origins. |
| `FRONTEND_URL` | `http://localhost:5173` | Used in OAuth return + CORS. |
| `BACKEND_URL` | `http://localhost:8000` | Used in OAuth redirect URI. |
| `FILE_STORAGE_PATH` | `backend/uploads` | Document storage root. |
| `EMAIL_SYNC_INTERVAL_MINUTES` | 60 | Background scan cadence. |
| `GMAIL_CREDENTIALS_FILE` | `backend/credentials.json` | OAuth client_secrets. |
| `GMAIL_REDIRECT_URI` | `BACKEND_URL/gmail/callback` | OAuth redirect. |
| `GMAIL_SYNC_DAYS` | 7 | Lookback window. |
| `GMAIL_SYNC_MAX_MESSAGES` | 100 | Per-sync cap. |
| `GMAIL_PREFER_UNREAD` | false | If true, only fetch unread. |
| `GMAIL_DISABLED` | false | Kill-switch — every `/gmail/*` returns 503. |

---

## Safety guarantees in code

These are enforced in code (not policy):

1. **No DB resets** — there is no `DROP TABLE` / `Base.metadata.drop_all`
   path in production code.
2. **No hard deletes of documents** — archive-only via `archived=true`
   on `email_attachments`. The QC archive flow has a `delete_file`
   mode but it requires the user to type "DELETE".
3. **No silent overwrites of manual edits** — `manual_overrides`
   metadata makes the auto-apply path skip any field a human
   touched and create a `needs_review` alert instead.
4. **APPLY / ROLLBACK / DELETE / CREATE ANYWAY** — every irreversible
   action requires an exact-string confirmation in the request body
   AND the UI requires the user to type the same string in a confirm
   modal. Server re-validates so the UI cannot be bypassed.
5. **Full audit log** — `shipment_events` for shipment writes,
   `document_assignment_actions` for QC actions,
   `import_batches.details_json` for every imported row.
