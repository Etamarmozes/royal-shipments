# Frontend Screens

_Generated: 2026-05-03 — point-in-time snapshot._

This document lists every page in the app, where it lives in the
codebase, who can access it, what it shows, and what backend
endpoints it calls.

Status taxonomy: ✅ Working / 🟡 Partial / ❓ Needs verification.

## Public routes

### `/login` — `pages/Login.tsx`

- **Role:** unauthenticated
- **Purpose:** Username + password login.
- **APIs:** `POST /auth/login`
- **Status:** ✅ Working
- **Notes:** Hebrew error messages. After success, redirects to
  `/change-password` if `must_change_password=true`, otherwise to
  the destination originally requested (default `/`).

### `/change-password` — `pages/ChangePassword.tsx`

- **Role:** authenticated (any role)
- **Purpose:** Force password change after first login or admin reset.
- **APIs:** `POST /auth/change-password`
- **Status:** ✅ Working

---

## Protected routes (require login)

All routes below live under `<ProtectedRoute>` + `<Layout>`. The
sidebar (`components/Layout.tsx`) hides items the role cannot use.

### `/` (index) — `pages/Dashboard.tsx`

- **Role:** all authenticated users
- **Purpose:** Operational dashboard. KPI tiles, action items,
  forecast snapshot, daily pallet forecast.
- **APIs:** `GET /dashboard/kpis`, `/dashboard/forecast-8-weeks`,
  `/dashboard/email-summary`, `/dashboard/extra-work-summary`,
  `/dashboard/action-items`, `/dashboard/pallet-kpis`,
  `/dashboard/pallet-forecast-daily`
- **Status:** ✅ Working

### `/shipments` — `pages/Shipments.tsx`

- **Role:** all
- **Purpose:** List of active shipments with filters + search +
  archive toggle.
- **APIs:** `GET /shipments`, `GET /shipments/categories/list`,
  `DELETE /shipments/:id` (archive)
- **Status:** ✅ Working

### `/shipments/:id` — `pages/ShipmentProfile.tsx`

- **Role:** all (read); admin / import_manager / warehouse for writes
- **Purpose:** Full per-shipment view + editor + documents + events
  + AI panel + smart-doc-status panel + container list.
- **APIs (read):** `GET /shipments/:id`, `/shipments/:id/documents`,
  `/shipments/:id/events`, `/shipments/:id/data-quality`,
  `/shipments/:id/document-status`, `/documents/required-status/:id`,
  `/containers?shipment_id=:id`
- **APIs (write):** `PUT /shipments/:id`,
  `POST /shipments/:id/recalculate-document-status`,
  `POST /shipments/:id/product-image`,
  `DELETE /shipments/:id/product-image`,
  `POST /documents/:id/classify`, `/documents/:id/set-type`,
  `/documents/:id/mark-noise`, `/documents/:id/restore-as-document`
- **Status:** ✅ Working

### `/containers` — `pages/Containers.tsx`

- **Role:** all
- **Purpose:** All containers list with filters.
- **APIs:** `GET /containers`
- **Status:** ✅ Working

### `/containers/:id` — `pages/ContainerProfile.tsx`

- **Role:** all (read), admin/import_manager (write)
- **Purpose:** Per-container detail + pallet calculator + receiving
  shortcut.
- **APIs:** `GET /containers/:id`, `/containers/:id/pallet-breakdown`,
  `/containers/:id/data-quality`, `POST /containers/:id/calculate-pallets`
- **Status:** ✅ Working

### `/containers-in-transit` — `pages/ContainersInTransit.tsx`

- **Role:** all
- **Purpose:** Filtered container view — currently in transit.
- **APIs:** `GET /containers?status=in_transit` (or similar query)
- **Status:** ✅ Working

### `/categories` — `pages/Categories.tsx`

- **Role:** all
- **Purpose:** Per-category dashboard view.
- **APIs:** `GET /shipments/categories/list`, `GET /shipments?category=...`
- **Status:** ✅ Working

### `/documents` — `pages/Documents.tsx`

- **Role:** all (read); upload requires `document.upload`
- **Purpose:** Cross-shipment documents browser. Filter by type,
  shipment, sender. Upload new docs. Reclassify, mark noise,
  reassign.
- **APIs:** `GET /documents`, `GET /documents/filtered-noise`,
  `POST /documents/upload`, `POST /documents/classify-all`,
  `POST /documents/auto-link`, `POST /documents/redownload-invalid`,
  `PUT /documents/:id/assign`, `PUT /documents/:id/document-type`,
  `POST /documents/:id/classify`, `POST /documents/:id/set-type`,
  `POST /documents/:id/mark-noise`,
  `POST /documents/:id/restore-as-document`
- **Status:** ✅ Working

### `/receiving` — `pages/Receiving.tsx`

- **Role:** all (read); `receiving.update` for receive
- **Purpose:** Warehouse worklist — containers expected at
  warehouse. Per-container receive form (cartons, pallets, notes,
  status).
- **APIs:** `GET /receiving/queue`,
  `GET /receiving/container/:id`,
  `POST /receiving/container/:id/receive`
- **Status:** ✅ Working

### `/help/supplier` — `pages/SupplierHelp.tsx`

- **Role:** all
- **Purpose:** Reference page for suppliers — what data we need from
  them, format expectations.
- **APIs:** `GET /shipments/help/supplier-doc`
- **Status:** ✅ Working (static-ish)

### `/users` — `pages/Users.tsx`

- **Role:** admin only (route-level `requireRole=["admin"]`)
- **Purpose:** Users + role management. Reset passwords.
- **APIs:** `GET /users`, `POST /users`, `PUT /users/:id`,
  `POST /users/:id/reset-password`, `GET /users/roles/list`
- **Status:** ✅ Working

### `/forecast` — `pages/Forecast.tsx`

- **Role:** all
- **Purpose:** 8-week container forecast.
- **APIs:** `GET /dashboard/forecast-8-weeks`
- **Status:** ✅ Working

### `/forecast-daily` — `pages/DailyForecast.tsx`

- **Role:** all
- **Purpose:** Daily pallet forecast for warehouse capacity.
- **APIs:** `GET /dashboard/pallet-forecast-daily`,
  `/dashboard/pallet-kpis`
- **Status:** ✅ Working

### `/email-updates` — `pages/EmailUpdates.tsx`

- **Role:** admin / import_manager
- **Purpose:** Approve / reject / assign / reprocess inbound email
  updates. Inject manual email for testing.
- **APIs:** `GET /email/updates`, `GET /email/updates/:id`,
  `PUT /email/updates/:id/approve`,
  `PUT /email/updates/:id/reject`,
  `PUT /email/updates/:id/assign-shipment`,
  `PUT /email/updates/:id/reprocess`,
  `POST /email/sync-now`,
  `POST /email/process-fetched`,
  `POST /email/inject`,
  `GET /gmail/status`, `POST /gmail/sync`
- **Status:** ✅ Working (real Gmail flow ❓ needs verification — see
  CURRENT_STATUS)

### `/pending-shipments` — `pages/PendingShipments.tsx`

- **Role:** admin / import_manager (per route nav rule)
- **Purpose:** New-shipment proposals from emails awaiting human
  approval. Approve / reject / assign-to-existing / edit before
  approve.
- **APIs:** `GET /pending-shipments`, `GET /pending-shipments/:id`,
  `PUT /pending-shipments/:id`,
  `POST /pending-shipments/:id/approve`,
  `POST /pending-shipments/:id/reject`,
  `POST /pending-shipments/:id/assign-to-existing-shipment`
- **Status:** ✅ Working

### `/extra-work` — `pages/ExtraWork.tsx`

- **Role:** all (read); admin/import_manager (write)
- **Purpose:** All extra-work tasks list + create + edit + complete
  + delay.
- **APIs:** `GET /extra-work`, `POST /extra-work`,
  `PUT /extra-work/:id`, `PUT /extra-work/:id/complete`,
  `PUT /extra-work/:id/delay`
- **Status:** ✅ Working

### `/alerts` — `pages/Alerts.tsx`

- **Role:** all (read); admin/import_manager (resolve)
- **Purpose:** Active alerts. Resolve.
- **APIs:** `GET /alerts`, `PUT /alerts/:id/resolve`,
  `POST /alerts/scan`
- **Status:** ✅ Working

### `/history` — `pages/History.tsx`

- **Role:** all
- **Purpose:** Audit log browser. Filter by entity type, actor, date.
- **APIs:** `GET /events?...`
- **Status:** ✅ Working

### `/data-review` — `pages/DataReview.tsx`

- **Role:** admin / import_manager (route guard)
- **Purpose:** Data Review — find malformed / suspicious / test
  shipments. Bulk-flag as test data. Purge test data (admin only).
- **APIs:** `GET /data-review`, `PATCH /data-review/:id`,
  `PATCH /data-review/bulk-flag`, `GET /data-review/documents`,
  `POST /data-review/purge-test-data`
- **Status:** ✅ Working

### `/document-review` — `pages/DocumentAssignmentReview.tsx`

- **Role:** admin / import_manager
- **Purpose:** Operational console for the Document Assignment QC
  layer. Per-row buttons: הצג / הורד / שייך / נתק / ✓ תקין /
  ☐ לבדיקה / ארכב. Bulk multi-select. ReassignModal with shipment
  search. ArchiveModal with 3 modes (record_only / archive_file /
  delete_file requires DELETE confirm).
- **APIs:** `GET /qc/documents`, `GET /qc/summary`,
  `GET /qc/documents/by-shipment/:id`,
  `POST /qc/documents/run`,
  `POST /qc/documents/:result_id/approve`,
  `POST /qc/documents/:result_id/archive`,
  `GET /qc/rules`, `POST /qc/rules`, `PUT /qc/rules/:id`,
  `POST /qc/rules/:id/deactivate`,
  `GET /shipments/search?q=...`,
  `GET /documents/:id/file-status`,
  `GET /documents/:id/possible-matches`
- **Status:** ✅ Working

### `/import-excel` — `pages/ImportExcel.tsx`

- **Role:** admin / import_manager
- **Purpose:** Multi-format Excel preview + apply (3-step wizard).
  Drag-drop file → preview rows with match badges → apply.
- **APIs:** `GET /import/excel/template` (download Royal Linen
  template), `POST /import/excel/preview`, `POST /import/excel/apply`
- **Status:** ✅ Working
- **Notes:**
  - Match badges: red (exact), orange (strong), yellow (soft), none
    (no match).
  - "CREATE ANYWAY" modal blocks unsafe creates by default.
  - Server re-validates the dedup safety gate.

### `/import-batches` — `pages/ImportBatches.tsx`

- **Role:** admin / import_manager
- **Purpose:** List of all import batches + per-batch detail +
  rollback ("ROLLBACK" confirmation).
- **APIs:** `GET /import/batches`, `GET /import/batches/:id`,
  `POST /import/batches/:id/rollback`
- **Status:** ✅ Working
- **Notes:** Lists `live_shipments` and flags any with
  `had_post_import_edits=true` so rollback isn't done blindly.

---

## Shared components

- `components/Layout.tsx` — sidebar navigation, mobile drawer + bottom
  nav, role-aware item filtering, AI assistant button.
- `components/AIAssistant.tsx` — floating AI panel.
- `components/AIPanel.tsx` — page-embedded AI panel with structured
  answer display + sources.
- `components/DocumentCard.tsx` — classification badge, reclassify
  menu (`⋯`), 🔒 manual icon, manual classify dropdown.
- `components/AuthedImage.tsx` — `<img>` whose `src` is a Blob URL
  obtained via authenticated fetch.
- `components/ArrivalsTimeline.tsx` — timeline visualization for
  shipment arrivals.
- `components/DataQuality.tsx` — per-shipment / per-container data
  quality score badge.
- `components/ExcelPreview.tsx` — render an Excel sheet inside a
  modal (used by document preview).
- `components/ErrorBoundary.tsx` — top-level error boundary.
- `components/common.tsx` — small shared atoms (Empty, Spinner,
  badges).

---

## Mobile UX

- Mobile uses a bottom navigation bar with 4 quick actions:
  בית (`/`), מכולות (`/containers-in-transit`), קבלה
  (`/receiving`), מסמכים (`/documents`), and an "עוד" button that
  opens the full sidebar drawer.
- Bottom nav respects `env(safe-area-inset-bottom)` for iOS notch.
- The desktop sidebar (≥ `lg`) is fixed-position on the right (RTL).

---

## Internationalization

- All user-facing text is Hebrew (RTL).
- The app sets `dir="rtl"` at the HTML root (`index.html`).
- Tailwind RTL utilities + the standard `ltr:` / `rtl:` modifiers are
  used where layout differs.
- Date formatting uses `date-fns` with the Hebrew locale.
- Internal route paths and TypeScript identifiers remain English.
