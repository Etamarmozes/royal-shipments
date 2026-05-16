# Royal Linen Shipments — App Overview

_Generated: 2026-05-03 — point-in-time snapshot._

## What this app is

Royal Linen Shipments is an internal Hebrew/RTL operational web
application that tracks every step of an inbound import shipment for
Royal Linen Ltd, from the moment a supplier confirms an order until the
goods are received in the warehouse and distributed to branches.

The app replaces the company's previous workflow of tracking shipments
across spreadsheets, emails and WhatsApp. It centralises all sources
(supplier emails, freight-forwarder Excel files, customs broker
documents, warehouse receiving) into a single source of truth with a
full audit log.

## Who uses it (roles)

The roles are enforced both server-side (FastAPI dependency
`require_permission`) and surfaced to the UI via `/auth/me.permissions`.

| Role | Hebrew | Typical user | What they do |
| --- | --- | --- | --- |
| `admin` | מנהל | Owner / system admin | Everything, including user management, rollbacks, deletes. |
| `import_manager` | מנהל יבוא | Import operations team | Create + edit shipments, approve email updates, run Excel imports, run QC, manage extra-work tasks. |
| `warehouse` | מחסן | Warehouse staff | Read-only on shipments. Receive containers, upload documents, upload product images. |
| `viewer` | צופה | Management / read-only stakeholders | Read-only across everything. Can ask the AI assistant. |

The app currently has **21 users** in the database
(`SELECT COUNT(*) FROM users`).

> **Update (full operational reset, 2026-05-03 20:17:52):** A
> controlled full operational reset has now been executed. All 13
> operational tables (shipments, containers, documents, events,
> alerts, batches, etc.) are empty. Users + document assignment rules
> were preserved. A DB backup, audit Excel export, log file, and the
> physical files (moved, not deleted) live under `backend/data/backups/`,
> `backend/exports/`, `backend/logs/`, and
> `backend/uploads/archive_before_reset/20260503_201752/`. See
> `CURRENT_STATUS_AND_NEXT_STEPS.md` for full counts and recovery
> instructions.

## Modules at a glance

The application is organised around the following modules. Each one is
fully wired (route exists, backend endpoint exists, frontend calls it)
unless explicitly noted otherwise.

### 1. Operational dashboard
- KPI tiles, action items, 8-week forecast, daily pallet forecast.
- Sources: `/dashboard/*` endpoints.

### 2. Shipment lifecycle
- 9-stage shipment funnel from order → ETD → port arrival → customs →
  warehouse → distribution.
- Per-shipment profile page with documents, containers, events history,
  AI assistant panel.
- Manual-override metadata (`manual_overrides`) protects fields that a
  user has hand-edited from being silently overwritten by automated
  email updates.

### 3. Container & pallet planning
- Container-level tracking (CBM, cartons, ETA, receiving status).
- Pallet calculator with per-container breakdown (Euro vs Industrial).
- Daily pallet forecast for warehouse capacity planning.

### 4. Documents
- Documents are stored as `email_attachments` (one table covers both
  Gmail-fetched and manually-uploaded files — it is the unified
  document store).
- Document Intelligence layer classifies each file (Invoice / Packing
  List / BOL / HBL / MBL / PO / Customs / Certificate / Product Image /
  Email Noise) and computes per-shipment "do we have the required docs?"
  status.
- Manual override of classification is supported with a 🔒 icon
  marker.

### 5. Document Assignment QC
- Audit-only background scan that detects "this document looks like it
  was wrongly assigned to shipment X — it likely belongs to Y."
- Surfaces verdicts (open / approved_keep / approved_move /
  approved_detach) without ever auto-mutating the document↔shipment
  link.
- Operational console at `/document-review` lets the import manager
  view, download, reassign, detach, mark as correct, mark for review,
  or archive each suspicious document, with a full audit trail in
  `document_assignment_actions`.

### 6. Email-driven updates
- Manual or Gmail-fetched emails are parsed into `email_updates` rows.
- Auto-apply policy: trusted high-confidence updates apply themselves
  (and create a "needs review" alert when a manual override would have
  been overwritten); ambiguous ones go to the approval queue at
  `/email-updates`.
- Pending-shipment workflow: emails that look like a brand-new
  shipment land in `/pending-shipments` for explicit human approval.

### 7. Excel import — multi-format
- Three Excel formats are detected automatically:
  - **Royal Linen Template** — our own template, full preview + apply.
  - **ICL** — freight-forwarder ICL "Open Import Orders & Files" sheet,
    full preview + apply with import-batch tracking.
  - **Eli Line** — Eli Line freight forwarder sheet ("גיליון1" /
    ASHDOD section), full preview + apply with import-batch tracking.
- The preview step runs a 0–100 dedup score against existing shipments
  and surfaces 4 match levels: `exact_duplicate`, `strong_possible_match`,
  `soft_possible_match`, `no_match`.
- "Create" actions on `exact_duplicate` or `strong_possible_match` rows
  are blocked unless the user types "CREATE ANYWAY" in the UI's
  confirmation modal (which sets `_force_create=true` per row). The
  apply endpoint re-validates this server-side before writing.

### 8. Import batches & rollback
- Every external-format apply creates an `import_batches` row.
- Each created shipment carries `import_batch_id` for provenance.
- `/import-batches` lists all batches and shows live shipments still
  pointing to each.
- Rollback archives only shipments where
  `import_batch_id == X AND creation_source == "excel_import_external"`,
  and requires the user to type "ROLLBACK". UPDATE actions are NOT
  auto-reverted (no automatic undo of field-level changes).

### 9. Warehouse receiving
- `/receiving` shows the inbound container queue ordered by warehouse
  ETA.
- Per-container "receive" form captures actual carton/pallet counts,
  receiving notes, and resolves any discrepancy state.

### 10. Extra-work tasks
- Per-shipment extra-work tasks (sticker change, repacking, vendor
  rework). Each task tracks expected/actual dates, responsible party,
  ready-for-distribution date, branch entry date.

### 11. Alerts
- Background scan generates alerts for: missing documents at late
  stage, ETA changed via email, paperwork missing, awaiting approval,
  email-update needs review, receiving carton discrepancy, etc.
- 50 alerts currently exist (mix of resolved and unresolved).

### 12. AI assistant
- Rule-based (no LLM). Lives as a panel on every shipment / container
  / page-level context.
- `/ai/ask` answers structured questions like "is paperwork complete?",
  "when does this arrive?", "which containers are delayed?".
- Suggested-question chips per page.

### 13. Audit / history
- Every write to a tracked field on a shipment, container, or extra-work
  task creates a `shipment_events` row with old/new value, actor, and
  source.
- 294 events currently in the DB. The history page lists them
  filterable by entity / actor / date.

## Hebrew + RTL

The entire UI is right-to-left Hebrew. All user-facing labels,
error messages, sidebar items, modals, badges, and confirmations are
in Hebrew. Internal/code identifiers remain English (English route
paths, English DB columns, English backend logs) so the codebase is
maintainable by non-Hebrew-speaking engineers.

## Authentication

- Username + password (bcrypt-hashed) → JWT with 24h TTL.
- No Google login dependency for app login. The `/gmail/*` routes use
  Google OAuth only for email integration, not for app authentication.
- A bootstrap admin (`admin` / `123456`, must change on first login) is
  created automatically if no users exist.
- An emergency env-var admin (`EMERGENCY_ADMIN_USERNAME` /
  `EMERGENCY_ADMIN_PASSWORD`) can break-glass log in even if the DB
  users table is empty/locked.

## Deployment shape

- Backend: FastAPI + SQLAlchemy 2 + SQLite (dev) / Postgres (prod-ready
  via `DATABASE_URL`). Background scheduler (APScheduler) runs the
  hourly alert + email-sync + QC scans.
- Frontend: React 18 + TypeScript + Vite + Tailwind, RTL.
- Single-machine local dev: backend on `:8000`, frontend on `:5173`.
- PWA-capable (manifest, service worker, offline.html).

## Repository layout

```
royal-linen-shipments-app/
├── backend/
│   ├── app/
│   │   ├── routers/        ← 21 FastAPI routers
│   │   ├── services/       ← 30 service modules
│   │   ├── models/         ← 10 SQLAlchemy model files
│   │   ├── schemas/        ← Pydantic v2 schemas
│   │   ├── utils/migrations.py  ← additive-only column migrations
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── main.py
│   │   └── seed.py
│   ├── data/royal_linen.db (SQLite)
│   ├── uploads/            ← document storage
│   ├── scripts/check_app_health.py
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── pages/          ← 25 page components
│   │   ├── components/     ← 10 shared components
│   │   ├── api/            ← typed API client
│   │   ├── auth/           ← auth store + ProtectedRoute
│   │   ├── hooks/
│   │   ├── utils/          ← fileAccess (authed downloads), format helpers
│   │   ├── types/index.ts  ← shared TS types
│   │   ├── App.tsx
│   │   └── main.tsx
│   └── package.json
└── docs/                   ← this folder
```
