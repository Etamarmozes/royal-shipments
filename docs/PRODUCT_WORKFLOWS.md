# Product Workflows

_Generated: 2026-05-03 — point-in-time snapshot._

This document walks through the user-visible workflows that exist
today, what each one is supposed to do, and what is fully working vs
partially-built. Status taxonomy:

- ✅ **Working** — end-to-end wired (backend route + frontend call +
  build green). Tested at least once during development.
- 🟡 **Partial** — wired but with caveats noted inline.
- 🔵 **Backend exists, frontend missing** — endpoint works, no UI
  surface yet.
- ⚪ **Frontend exists, backend missing**.
- 🔴 **Planned only**.
- ❓ **Needs verification** — wired but I have not personally exercised
  it end-to-end since the last code change.

---

## 1. Login + first-time password change

**Status: ✅ Working.**

1. User opens the app. `ProtectedRoute` redirects unauthenticated users
   to `/login`.
2. `/login` calls `POST /auth/login` with username + password.
3. Backend (`backend/app/routers/auth.py`) verifies bcrypt hash, returns
   JWT (HS256, 24h TTL) + user object.
4. Frontend stores the token in `localStorage` and adds it to every
   subsequent request via the axios interceptor (`api/client.ts`).
5. If `must_change_password=true` (only the bootstrap admin or
   admin-reset users), the UI redirects to `/change-password` and
   blocks all other navigation until the password is changed.
6. `GET /auth/me` returns the user + the precomputed list of allowed
   permissions; the frontend uses that list to hide buttons the role
   cannot use.

Bootstrap admin: `admin / 123456`, force-change on first login.
Emergency admin: env-var `EMERGENCY_ADMIN_USERNAME` /
`EMERGENCY_ADMIN_PASSWORD` always works regardless of DB state.

---

## 2. Browse + edit a shipment

**Status: ✅ Working.**

### Listing

- `/shipments` (`Shipments.tsx`) lists active (non-archived) shipments
  with filters (search, current_stage, supplier, category, archive
  toggle).
- The list uses `GET /shipments` with query params. The DB currently
  has **0 shipments** total (post full operational reset
  2026-05-03 20:17:52; see `CURRENT_STATUS_AND_NEXT_STEPS.md`).

### Profile page

- `/shipments/:id` (`ShipmentProfile.tsx`) shows everything for one
  shipment:
  - Header (SHP-id, supplier, current stage, ETA badges).
  - Editable fields panel (ETA, category, notes, etc.). Each save
    is checked for permission errors and shows a clear save-error
    banner if the API rejects.
  - Per-field 🔒 marker for fields recorded in `manual_overrides`.
  - Containers list with pallet calc actions.
  - Smart Document Status panel (3 tiles for invoice / packing list /
    BL) with recalc button + "show N filtered noise" toggle.
  - Documents grid (`DocumentCard`) with classification badges and
    a `⋯ Reclassify` menu.
  - Events history, AI assistant panel, extra-work tasks.

### Edit-save guarantees

- Every save calls `PUT /shipments/:id` and responds with the updated
  shipment.
- The backend writes `shipment_events` rows for every tracked field
  change, including a `manual_overrides` entry recording WHO changed
  it and WHEN.
- After save, the frontend refetches the shipment with the new
  `updated_at` and re-syncs the form, so a "looked saved but vanished"
  ghost-edit is impossible.

### Tracked fields list

`SHIPMENT_TRACKED_FIELDS` (in `services/shipment_service.py`) currently
includes: ETA fields, supplier, goods_description, customs_broker,
booking_number, BOL/HBL/MBL, invoice_number, po_number, freight_price,
goods_value, paperwork_complete, approval_status, delay_status,
delay_reason, notes, **category**, current_stage, **extra_work_note**.
Manual edits to any of these create both an audit row and a
`manual_overrides` entry.

---

## 3. Documents — view, classify, reassign, archive

**Status: ✅ Working.**

### Storage

All documents live in `email_attachments`:
- Files fetched from Gmail attachments come in via the email sync.
- Files manually uploaded via `/documents/upload` synthesise an
  `EmailUpdate` row marked `status="manual_upload"` so the same table
  can hold them.
- Files on disk are under `backend/uploads/`. Filenames preserve the
  original extension; paths are stored in `file_path`.

### Authenticated downloads

The `<DocumentCard>` and shipment profile use
`utils/fileAccess.ts → useAuthedFile(url)` which performs an
authenticated `fetch` against `GET /documents/:id/download` and
creates a `Blob` URL the browser can render or save. This is the
pattern that prevented earlier "download leaks token in URL" issues.

### Classification (Document Intelligence)

`POST /documents/:id/classify` runs the rule-based classifier
(`services/document_classifier_service.py`). The classifier first
inspects the **filename**, then falls back to email subject/body —
this ordering fixed an earlier bug where "PL - ROYALL.pdf" was
mis-classified as a commercial invoice because the parent email
subject contained the word "Inventory".

Vocabulary (15 classes including 3 image classes and 1 noise
class): see `DATA_MODEL_SUMMARY.md`.

`POST /documents/classify-all` re-runs the classifier across every
non-archived attachment (used after rule changes).

### Smart document status per shipment

`GET /documents/required-status/:shipment_id` returns:
- Legacy `{present, missing, is_complete}` for backward compat with
  older UI code.
- New `by_type` dict per document type with status ∈ {missing,
  document_exists, data_extracted, needs_review, approved}.

`POST /shipments/:id/recalculate-document-status` re-runs the per-shipment
status panel.

### Reassign / detach

- `PUT /documents/:id/assign` changes `linked_shipment_id` /
  `linked_container_id`.
- `POST /documents/:id/mark-noise` and
  `POST /documents/:id/restore-as-document` toggle the
  `is_email_noise` flag without deleting the file.

### Archive (soft)

The DB columns `archived`, `archived_at`, `archived_by`,
`archived_reason`, `archived_mode` exist on `email_attachments`.
Archive happens via the QC console (see Workflow 4) — there is
no `/documents/:id/archive` route on the documents router itself;
the archive flow lives on the `document_qc` router.

### Manual classification override

`POST /documents/:id/set-type` sets the classification + records
`manually_classified_by` and `manually_classified_at`. The 🔒 icon
on the document card reflects this state.

---

## 4. Document Assignment QC console

**Status: ✅ Working.** Operational console at `/document-review`.

### Background scan

`document_qc_service.run_scan(db)` is invoked hourly by the scheduler
in `main.py`. It scores each document↔shipment link against the
configured rules + matching engine and writes one
`document_assignment_qc_results` row per (document, scan_run) with:
- `confidence_score` (0-100),
- `severity` ∈ {ok, minor, suspicious, strong_mismatch},
- `recommendation` ∈ {keep, review, reassign_suggested,
  detach_suggested},
- `mismatch_reasons_json` + `matched_signals_json` for explainability.

The scan is **audit-only** — it never mutates the assignment.

### UI (`DocumentAssignmentReview.tsx`)

For each suspicious assignment, the import manager sees:
- Filename, current shipment, suspected shipment, score, reasons.
- Action buttons:
  - הצג (Preview)
  - הורד (Download)
  - שייך (Reassign — opens `<ReassignModal>` with shipment search)
  - נתק (Detach)
  - ✓ תקין (Mark correct — `approved_keep`)
  - ☐ לבדיקה (Mark for later review)
  - ארכב (Archive — opens `<ArchiveModal>` with 3 modes:
    `archive_record_only` / `archive_file` / `delete_file`; the
    `delete_file` mode requires typing "DELETE" to confirm.)
- Bulk actions for multi-select rows.

### Audit

Every QC action writes a row to `document_assignment_actions` with
old/new shipment id, before/after JSON, action type, reason, actor.
There are currently 39 such rows in the DB.

### Counts (current snapshot)

- 46 QC results total.
- 33 `approved_move`, 3 `approved_detach`, 2 `approved_keep`,
  8 `open` (open = pending review).

---

## 5. Excel import — preview + apply (multi-format)

**Status: ✅ Working** for ICL, Eli Line, and Royal Linen Template.

### Step 1 — upload + format detection

User goes to `/import-excel`, drops a file. The frontend calls
`POST /import/excel/preview` with multipart form data.

The backend (`services/excel_format_detector.py`) detects the format:
- `royal_linen_template` — sentinel technical-key row.
- `icl` — sheet name "Open Import Orders & Files" or row-15 header
  signature.
- `eli_line` — row 1 contains "תאריך הגעה משוער" + "JOB".

Each format has a dedicated parser
(`services/external_excel_parsers.py` + `services/excel_import_service.py`).

### Step 2 — preview rows (no DB writes)

The preview endpoint never writes. For each parsed row it runs the
0-100 dedup score (`services/external_dedup_service.py`) against
existing shipments and returns:

```json
{
  "format": "icl",
  "format_info": { "sheet_name": "...", "header_row": 15, ... },
  "file_errors": [],
  "rows": [
    {
      "source_row_number": 17,
      "supplier": "...",
      "shipment_reference": "JOB-28060",
      ...,
      "_match_level": "exact_duplicate",
      "_match_score": 100,
      "_match_reasons": ["shipment_reference exact match"],
      "_possible_matches": [ {top-3 candidates} ],
      "_action_default": "update"   // smart default per match level
    }
  ],
  "summary": {
    "total_rows": ..., "create": ..., "update": ..., "skip": ...,
    "needs_review": ..., "exact_duplicate": ..., "strong": ..., "soft": ...
  },
  "applyable": true
}
```

### Step 3 — review per row

The UI (`ImportExcel.tsx`) shows each row with:
- A `<MatchBadge>` (red = exact duplicate, orange = strong, yellow =
  soft, none = no match).
- The top-3 candidate matches expandable.
- Action selector: create / update / skip.
- For `exact_duplicate` or `strong_possible_match` rows where the user
  wants to create anyway, a `<ForceCreateModal>` requires typing
  "CREATE ANYWAY" — that sets `_force_create=true` on the row.

### Step 4 — apply

`POST /import/excel/apply` requires `confirm: "APPLY"` in the body.

- Apply re-runs dedup server-side and rejects any `create` action on
  an unsafe-level row that does not carry `_force_create=true`.
- For ICL / Eli Line rows: the backend creates an `import_batches`
  row, sets `creation_source="excel_import_external"`, fills
  `import_batch_id`, `source_provider`, `source_row_number`,
  `raw_source_json` on each created shipment.
- ICL / Eli Line files give us container quantity + type but not
  actual container numbers, so the apply path creates **placeholder
  containers** with `placeholder_container=True` and
  `actual_container_number_missing=True`. The user later fills in the
  real numbers from the BL.
- Returns: `{batch_id, created, updated, skipped, errors, per_row}`.

### Status caveats

- Apply path for **Royal Linen Template** existed before the external
  formats and follows a separate code path
  (`excel_import_service.apply`). ❓ Needs re-verification end-to-end
  on a real template file.
- ICL / Eli Line apply path: ✅ Verified during the dev session via
  synthetic test workbooks; verified the dedup safety gate blocks
  exact-duplicate creates without `_force_create`.

---

## 6. Import Batches + rollback

**Status: ✅ Working.** UI at `/import-batches`.

`GET /import/batches` lists all batches.
`GET /import/batches/:id` returns one batch + the live (non-archived)
shipments still pointing to it, including `had_post_import_edits`
(true if the shipment has any `manual_overrides`).

`POST /import/batches/:id/rollback` requires `confirm: "ROLLBACK"`.
Archives every shipment where:
- `import_batch_id == batch_id` AND
- `creation_source == "excel_import_external"`.

It does **not** revert UPDATE actions (no per-field undo). It does
**not** delete files. The user can also see in the UI which shipments
have post-import edits and so should not be auto-rolled-back.

### Current state (post-cleanup snapshot, 2026-05-03 16:18 UTC)

13 batches in the DB. 11 are `rolled_back` (mostly tiny dev/QA
batches). 2 are `applied` with 0 created (no-op QA batches). The 16
JOB-* shipments that were created via the legacy `excel_import` path
(not `excel_import_external`) were soft-archived manually — they had
no `import_batch_id` so batch rollback was not applicable. The next
real ICL/Eli Line import via `/import-excel` will produce a proper
`import_batches` row.

---

## 7. Document Intelligence — recalculate + email noise filter

**Status: ✅ Working.**

- `POST /documents/classify-all` reclassifies every non-archived
  attachment.
- `GET /documents/filtered-noise` lists everything currently flagged
  as `is_email_noise=true` (10 such files in the DB, mostly
  `image001.png`-style logos and signatures).
- `POST /documents/:id/restore-as-document` un-flags an item that was
  wrongly marked as noise.
- `POST /documents/:id/mark-noise` flags an item as noise without
  deleting the file.

Smart status panel on the shipment profile shows: invoice, packing
list, BL — each as `missing` / `document_exists` / `data_extracted`
/ `needs_review` / `approved`. Recalc button on the panel triggers
`POST /shipments/:id/recalculate-document-status`.

---

## 8. Email-driven updates (Gmail integration)

**Status: 🟡 Partial — backend complete, depends on Gmail OAuth.**

### Sync

- `POST /gmail/sync` fetches recent emails (last 7 days, up to 100)
  via the Gmail API using the stored OAuth token.
- Each email is parsed by `services/email_parser_service.py` →
  `email_updates` row + attached `email_attachments`.
- Detection logic identifies whether the email is:
  - An update to an existing shipment (`detection_type=update_existing`),
  - A new shipment (`detection_type=new_shipment` → also creates
    `pending_shipments` row),
  - Ambiguous (`detection_type=needs_review`),
  - Irrelevant (`detection_type=irrelevant`).

### Auto-apply

`services/email_apply_service.py` auto-applies updates only when:
- `confidence_score` is high,
- No tracked field is in `manual_overrides`.
If a manual override would have been overwritten, the field is
**not** applied; instead a `flagged_fields_json` entry + a
`needs_review` alert is created.

### UI surfaces

- `/email-updates` — list of all email updates filterable by status.
- `/pending-shipments` — new-shipment proposals awaiting human
  approval.

### Caveats

- Gmail OAuth must be connected via `/gmail/connect` first. There is
  a kill-switch env var `GMAIL_DISABLED=true` that 503s every
  `/gmail/*` route — used when the Google account is unavailable.
- ❓ End-to-end Gmail sync has not been re-verified during the
  current dev session (focus was on the import + QC paths).

---

## 9. Pending shipments (new-shipment approval queue)

**Status: ✅ Working.** UI at `/pending-shipments`.

When an inbound email is detected as a new shipment, a
`pending_shipments` row + `pending_containers` are created. The
import manager reviews each one and either:
- Approves it (`POST /pending-shipments/:id/approve`) → creates a
  real `shipments` row + `containers`.
- Rejects it (`POST /pending-shipments/:id/reject`) with an optional
  rejection reason.
- Assigns it to an existing shipment
  (`POST /pending-shipments/:id/assign-to-existing-shipment`).

---

## 10. Warehouse receiving

**Status: ✅ Working.** UI at `/receiving`.

- `GET /receiving/queue` returns containers expected at the warehouse
  (`receiving_status` ∈ {not_received, partially_received, NULL})
  ordered by warehouse ETA, with attached document count.
- `GET /receiving/container/:id` returns the full per-container view
  with shipment context + linked documents.
- `POST /receiving/container/:id/receive` records actual cartons,
  pallets, notes, and the receiving status. The `received_by` field
  is forced to the authenticated user — staff can't impersonate.

---

## 11. Extra-work tasks

**Status: ✅ Working.** UI at `/extra-work`.

- `POST /extra-work` creates a task linked to a shipment (and
  optionally a container) with `work_type`, `responsible_party`,
  expected/actual dates.
- `PUT /extra-work/:id`, `PUT /extra-work/:id/complete`,
  `PUT /extra-work/:id/delay`.

---

## 12. Alerts

**Status: ✅ Working.** UI at `/alerts`.

`alert_service.scan_alerts(db)` runs hourly and creates alerts for:
- Missing required documents (invoice/PL/BL) at late stage.
- Paperwork incomplete at late stage.
- Awaiting approval (email_update or pending_shipment).
- Email update needs review (manual override would have been
  overwritten).
- ETA changed via email.
- Receiving carton discrepancy.
- Delay detected in email.

User resolves an alert via `PUT /alerts/:id/resolve`. Manual scan
trigger: `POST /alerts/scan`.

---

## 13. AI assistant

**Status: ✅ Working** (rule-based, no external LLM).

- Floating "AIAssistant" button on every page (component
  `<AIAssistant>`, mounted in `Layout.tsx`).
- Per-shipment "AIPanel" on the profile page.
- `POST /ai/ask` — accepts question + context (`shipment_id`,
  `container_id`, `page`); returns structured answer with intent,
  confidence, sources, and suggested actions.
- `GET /ai/suggestions?shipment_id=...` — context-appropriate
  suggested questions.

Implementation lives in `services/ai_assistant_service.py` and uses
intent matching + DB queries — there is no external API call to
Anthropic or OpenAI from this service.

---

## 14. Categories

**Status: ✅ Working.** UI at `/categories`.

Per-category dashboard view: which shipments are in transit,
arrival timeline, container counts. Categories are managed in
`services/category_service.py`.

---

## 15. History / events log

**Status: ✅ Working.** UI at `/history`.

- `GET /events?entity_type=...&entity_id=...&actor=...&from=...&to=...`
  returns a filtered audit log.
- 294 events currently in the DB.
- Per-shipment events also accessible via
  `GET /shipments/:id/events`.
