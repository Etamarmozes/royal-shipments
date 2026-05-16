# API Endpoints Summary

_Generated: 2026-05-03 — point-in-time snapshot._

Notes:
- All routes are auth-protected via the FastAPI `auth_dep` dependency
  set in `main.py`, except where explicitly noted.
- "Permission" refers to the entry in
  `services/auth_service.py:PERMISSIONS` enforced via
  `require_permission(...)` inside the route handler.
- Routes that don't carry an explicit permission still require a
  valid JWT (any logged-in user).

---

## Root + health (public-ish)

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| GET | `/` | none | App banner JSON. |
| GET | `/health` | none | `{status: "ok"}` for uptime checks. |

---

## `/auth` — `routers/auth.py` — public

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| POST | `/auth/login` | public | Username + password → JWT. |
| POST | `/auth/logout` | bearer | Stateless ack. |
| GET  | `/auth/me` | bearer | Current user + permission list. |
| POST | `/auth/change-password` | bearer | Change own password. |

---

## `/users` — `routers/users.py` — admin only

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| GET  | `/users` | admin | List users. |
| POST | `/users` | admin | Create user. |
| PUT  | `/users/:id` | admin | Update user (role, name, active). |
| POST | `/users/:id/reset-password` | admin | Reset password (force change on next login). |
| GET  | `/users/roles/list` | admin | Available roles + Hebrew labels. |

---

## `/shipments` — `routers/shipments.py`

| Method | Path | Permission | Description |
| --- | --- | --- | --- |
| GET  | `/shipments` | shipment.read | List + filter. Returns `{items, total}`. |
| GET  | `/shipments/categories/list` | shipment.read | Distinct categories. |
| GET  | `/shipments/search?q=...` | shipment.read | Free-text shipment search (used by reassign modal). MUST be declared before `/{id}` so `/search` doesn't collide with int parsing. |
| GET  | `/shipments/help/supplier-doc` | shipment.read | Supplier-help reference data. |
| GET  | `/shipments/:id` | shipment.read | One shipment. |
| POST | `/shipments` | shipment.create | Create. |
| PUT  | `/shipments/:id` | shipment.update | Update (writes audit + manual_overrides). |
| DELETE | `/shipments/:id` | shipment.archive | Soft-archive (`archived=true`), not hard delete. |
| POST | `/shipments/:id/recalculate-document-status` | shipment.read | Re-run smart doc status. |
| GET  | `/shipments/:id/document-status` | shipment.read | Quick legacy doc-status. |
| GET  | `/shipments/:id/data-quality` | shipment.read | Per-shipment data quality. |
| GET  | `/shipments/:id/documents` | shipment.read | Documents linked to this shipment (filtered to non-noise unless includeNoise=true). |
| GET  | `/shipments/:id/events` | shipment.read | Audit log filtered to this shipment. |
| POST | `/shipments/:id/product-image` | product_image.upload | Upload product photo. |
| DELETE | `/shipments/:id/product-image` | product_image.upload | Remove product photo. |
| GET  | `/shipments/:id/product-image` | shipment.read | Stream product image (auth required). |

---

## `/containers` — `routers/containers.py`

| Method | Path | Permission | Description |
| --- | --- | --- | --- |
| GET  | `/containers` | container.read | List + filter. |
| GET  | `/containers/:id` | container.read | One container. |
| POST | `/containers` | container.create | Create (with optional shipment_id). |
| PUT  | `/containers/:id` | container.update | Update (writes audit + manual_overrides). |
| DELETE | `/containers/:id` | container.delete | Delete (used during cleanup; not exposed as primary UI action). |
| POST | `/containers/:id/calculate-pallets` | container.update | Run pallet calculator + persist results. |
| GET  | `/containers/:id/data-quality` | container.read | Per-container quality. |
| GET  | `/containers/:id/pallet-breakdown` | container.read | Detailed Euro vs Industrial breakdown. |

---

## `/documents` — `routers/documents.py`

**Route order matters** — fixed-string subpaths are declared BEFORE
`/{doc_id}` to avoid the parametric route swallowing them.

| Method | Path | Permission | Description |
| --- | --- | --- | --- |
| GET  | `/documents` | document.read | List + filter. |
| GET  | `/documents/filtered-noise` | document.read | List items currently flagged as `is_email_noise=true`. |
| POST | `/documents/classify-all` | document.upload | Reclassify every non-archived attachment. |
| POST | `/documents/upload` | document.upload | Manual upload (creates synthetic email_update + attachment). |
| GET  | `/documents/required-status/:shipment_id` | document.read | Smart per-shipment doc status panel data. |
| POST | `/documents/auto-link` | document.assign | Auto-link unassigned documents by metadata. |
| POST | `/documents/redownload-invalid` | document.upload | Re-fetch attachments whose `file_path` is missing/broken. |
| GET  | `/documents/:id` | document.read | One document metadata. |
| GET  | `/documents/:id/download` | document.read | Stream the file (auth required). |
| GET  | `/documents/:id/preview` | document.read | Inline preview URL (PDF/image). |
| GET  | `/documents/:id/excel-preview` | document.read | Render xlsx as JSON for in-app modal. |
| GET  | `/documents/:id/file-status` | document.read | Is the on-disk file present + valid? |
| GET  | `/documents/:id/possible-matches` | document.read | Top-N candidate shipments for this doc. |
| POST | `/documents/:id/redownload` | document.upload | Re-fetch one attachment from Gmail. |
| PUT  | `/documents/:id/assign` | document.assign | Change `linked_shipment_id` / `linked_container_id`. |
| PUT  | `/documents/:id/document-type` | document.assign | Set legacy `document_type` field. |
| POST | `/documents/:id/classify` | document.upload | Run classifier on this single doc. |
| POST | `/documents/:id/set-type` | document.assign | Manually override classification. Sets `manually_classified_by/at`. |
| POST | `/documents/:id/mark-noise` | document.assign | Flag as `is_email_noise=true`. |
| POST | `/documents/:id/restore-as-document` | document.assign | Un-flag noise. |

---

## `/qc` — `routers/document_qc.py` — Document Assignment QC

| Method | Path | Permission | Description |
| --- | --- | --- | --- |
| GET  | `/qc/documents` | document.read | List QC results (open by default). |
| GET  | `/qc/summary` | document.read | Counts per status + severity. Used by health-check. |
| GET  | `/qc/documents/by-shipment/:shipment_id` | document.read | QC results filtered to one shipment. |
| POST | `/qc/documents/run` | document.upload | Manually trigger QC scan. |
| POST | `/qc/documents/:result_id/approve` | document.assign | Apply user decision (keep / move / detach / mark_correct / ignore). Writes audit row. |
| POST | `/qc/documents/:result_id/archive` | document.assign | Archive the underlying document with one of: `archive_record_only`, `archive_file`, `delete_file` (latter requires "DELETE" confirm). |
| GET  | `/qc/rules` | document.read | List supplier/brand rules. |
| POST | `/qc/rules` | users.manage (admin-ish) | Create rule. |
| PUT  | `/qc/rules/:id` | users.manage | Update rule. |
| POST | `/qc/rules/:id/deactivate` | users.manage | Soft-deactivate. |

---

## `/data-review` — `routers/data_review.py`

Admin / import_manager only (route guard).

| Method | Path | Description |
| --- | --- | --- |
| GET    | `/data-review` | Data quality + suspicious shipments list. |
| PATCH  | `/data-review/:shipment_id` | Update one row's flags / notes. |
| PATCH  | `/data-review/bulk-flag` | Bulk-flag rows as `is_test_data` (or unflag). |
| GET    | `/data-review/documents` | Data review focused on documents. |
| POST   | `/data-review/purge-test-data` | **Admin-only.** Permanently archive every row with `is_test_data=true` (requires confirmation). |

---

## `/import` — `routers/imports.py` — Excel multi-format

| Method | Path | Permission | Description |
| --- | --- | --- | --- |
| GET  | `/import/excel/template` | shipment.read | Download Royal Linen Excel template (.xlsx). |
| POST | `/import/excel/preview` | shipment.create | Preview rows + dedup verdict (no DB write). |
| POST | `/import/excel/apply` | shipment.create | Apply rows. Body must include `confirm: "APPLY"`. Server re-validates dedup safety gate. |
| GET  | `/import/batches` | shipment.read | List import batches. |
| GET  | `/import/batches/:id` | shipment.read | Batch detail + live shipments + `had_post_import_edits`. |
| POST | `/import/batches/:id/rollback` | shipment.archive | Rollback batch. Body must include `confirm: "ROLLBACK"`. Archives shipments where `import_batch_id=:id AND creation_source='excel_import_external'`. |

---

## `/email` — `routers/email_router.py`

| Method | Path | Permission | Description |
| --- | --- | --- | --- |
| POST | `/email/sync-now` | email.process | Stub sync — touch last_sync timestamp. Real Gmail sync is `/gmail/sync`. |
| POST | `/email/process-fetched` | email.process | Re-run parser on already-fetched email rows. |
| PUT  | `/email/updates/:id/reprocess` | email.process | Re-parse one email update. |
| POST | `/email/inject` | email.process | Inject a synthetic email update (used for testing the parser). |
| GET  | `/email/updates` | email.process (read variant) | List + filter email updates. |
| GET  | `/email/updates/:id` | email.process | One email update. |
| PUT  | `/email/updates/:id/approve` | email.approve | Approve auto-applied or pending update. |
| PUT  | `/email/updates/:id/reject` | email.reject | Reject. |
| PUT  | `/email/updates/:id/assign-shipment` | email.approve | Assign update to a specific shipment. |

---

## `/gmail` — `routers/gmail.py` — Google OAuth flow

These routes do NOT inherit the global auth dependency (the OAuth
callback can't carry a Bearer token). PKCE protects the auth code
exchange.

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| GET    | `/gmail/status` | bearer (manual check) | Connected? token present? last sync? |
| GET    | `/gmail/connect` | bearer | Returns a URL the UI redirects to. |
| GET    | `/gmail/callback` | none (PKCE) | Google's redirect target. Stores token JSON. |
| POST   | `/gmail/sync` | bearer + gmail.sync | Fetch recent emails, parse, persist. |
| POST   | `/gmail/backfill-attachments` | bearer + gmail.sync | Re-download missing attachments. |
| GET    | `/gmail/debug` | admin | Debug helper. |
| POST   | `/gmail/disconnect` | admin | Wipe token. |

If env `GMAIL_DISABLED=true`, every `/gmail/*` route returns 503.

---

## `/pending` (combined) — `routers/pending.py`

A unified queue of "things waiting for human approval" — both email
updates and pending shipments mixed together.

| Method | Path | Permission | Description |
| --- | --- | --- | --- |
| GET  | `/pending` | pending.approve | Combined list with counts. |
| POST | `/pending/:kind/:item_id/approve` | pending.approve | `kind=update` → email update; `kind=shipment` → pending shipment. |
| POST | `/pending/:kind/:item_id/reject` | pending.reject | Same dispatch. |

---

## `/pending-shipments` — `routers/pending_shipments.py`

| Method | Path | Permission | Description |
| --- | --- | --- | --- |
| GET  | `/pending-shipments` | pending.approve | List by status. |
| GET  | `/pending-shipments/:id` | pending.approve | One. |
| PUT  | `/pending-shipments/:id` | pending.approve | Edit detected fields before approving. |
| POST | `/pending-shipments/:id/approve` | pending.approve | Approve → creates real `shipments` + `containers`. |
| POST | `/pending-shipments/:id/reject` | pending.reject | Reject with optional reason. |
| POST | `/pending-shipments/:id/assign-to-existing-shipment` | pending.approve | Assign to an existing shipment_id. |

---

## `/extra-work` — `routers/extra_work.py`

| Method | Path | Permission | Description |
| --- | --- | --- | --- |
| GET  | `/extra-work` | shipment.read | List. |
| GET  | `/extra-work/:id` | shipment.read | One. |
| POST | `/extra-work` | extra_work.write | Create. |
| PUT  | `/extra-work/:id` | extra_work.write | Update. |
| PUT  | `/extra-work/:id/complete` | extra_work.write | Mark complete. |
| PUT  | `/extra-work/:id/delay` | extra_work.write | Mark delayed. |

---

## `/receiving` — `routers/receiving.py`

| Method | Path | Permission | Description |
| --- | --- | --- | --- |
| GET  | `/receiving/queue` | container.read | Containers expected at warehouse. |
| GET  | `/receiving/container/:id` | container.read | Per-container view. |
| POST | `/receiving/container/:id/receive` | receiving.update | Record actual cartons / pallets / notes / status. `received_by` forced to authenticated user. |

---

## `/dashboard` — `routers/dashboard.py`

| Method | Path | Description |
| --- | --- | --- |
| GET | `/dashboard/kpis` | KPI tiles. |
| GET | `/dashboard/forecast-8-weeks` | 8-week forecast. |
| GET | `/dashboard/email-summary` | Email funnel summary. |
| GET | `/dashboard/extra-work-summary` | Extra-work summary. |
| GET | `/dashboard/action-items` | Top action items. |
| GET | `/dashboard/pallet-forecast-daily` | Daily pallet forecast (default 14 days). |
| GET | `/dashboard/pallet-kpis` | Pallet KPIs. |

---

## `/alerts` — `routers/alerts.py`

| Method | Path | Permission | Description |
| --- | --- | --- | --- |
| GET  | `/alerts` | shipment.read | List + filter. |
| PUT  | `/alerts/:id/resolve` | alert.resolve | Resolve. |
| POST | `/alerts/scan` | alert.resolve | Manually trigger alert scan. |

---

## `/events` — `routers/events.py`

| Method | Path | Description |
| --- | --- | --- |
| GET | `/events?entity_type=...&entity_id=...&actor=...&from=...&to=...` | Filtered audit log. |

---

## `/export` — `routers/export.py`

| Method | Path | Description |
| --- | --- | --- |
| GET | `/export/excel?...` | Streams an .xlsx with the requested data slice. |

---

## `/ai` — `routers/ai.py`

| Method | Path | Permission | Description |
| --- | --- | --- | --- |
| POST | `/ai/ask` | ai.ask | Question + context → structured answer. |
| GET  | `/ai/suggestions?shipment_id=...` | ai.ask | Context-appropriate suggested questions. |

---

## Confirmation strings (irreversible actions)

These exact-string confirmations are required server-side:

| Action | Endpoint | Confirm string |
| --- | --- | --- |
| Excel apply (any provider) | `POST /import/excel/apply` | `"APPLY"` |
| Batch rollback | `POST /import/batches/:id/rollback` | `"ROLLBACK"` |
| Force-create over duplicate | `POST /import/excel/apply` (per row `_force_create=true`) | UI requires typing `"CREATE ANYWAY"` |
| Delete file (QC archive) | `POST /qc/documents/:id/archive` (mode=`delete_file`) | `"DELETE"` |
| Purge test data | `POST /data-review/purge-test-data` | implementation-specific (admin-only route) |

---

## Frontend ↔ backend wiring

The frontend's typed API client lives at `frontend/src/api/endpoints.ts`
(~900 lines). Every backend route used by the UI has a matching
typed wrapper. Notable wrappers:

- `listShipments`, `getShipment`, `createShipment`, `updateShipment`,
  `archiveShipment`, `shipmentEvents`, `searchShipments`
- `listContainers`, `getContainer`, `createContainer`, `updateContainer`,
  `deleteContainer`, `calculatePallets`, `getPalletBreakdown`
- `listDocuments`, `listShipmentDocuments`, `assignDocument`,
  `uploadDocument`, `requiredDocumentsStatus`, `documentDownloadUrl`,
  `documentPreviewUrl`, `classifyDocument`, `setDocumentType`,
  `markDocAsNoise`, `restoreDocAsDocument`, `listFilteredNoise`,
  `classifyAllDocuments`, `getSmartDocStatus`, `recalculateDocStatus`,
  `possibleMatches`, `fileStatus`, `excelPreview`,
  `redownloadDocument`, `redownloadInvalidDocuments`, `autoLinkDocuments`
- `listQcDocuments`, `qcSummary`, `runQcScan`, `qcApprove`, `qcArchive`,
  `listDocAssignmentReview`
- `previewExcelImport`, `applyExcelImport`, `listImportBatches`,
  `getImportBatch`, `rollbackImportBatch`, `importTemplateUrl`
- `listEmailUpdates`, `approveEmailUpdate`, `rejectEmailUpdate`,
  `assignEmailUpdate`, `reprocessEmail`, `syncEmailNow`,
  `processFetchedEmails`, `injectEmail`,
  `gmailStatus`, `gmailSync`, `gmailDisconnect`, `gmailConnectUrl`
- `listPending`, `approvePending`, `rejectPending`,
  `listPendingShipments`, `getPendingShipment`,
  `updatePendingShipment`, `approvePendingShipment`,
  `rejectPendingShipment`, `assignPendingToShipment`
- `dashboardKpis`, `dashboardForecast`, `dashboardActionItems`,
  `dashboardPalletKpis`, `dashboardPalletForecastDaily`
- `receivingQueue`, `getReceivingView`, `receiveContainer`
- `aiAsk`, `aiSuggestions`
- `listAlerts`, `resolveAlert`, `scanAlerts`
- `listExtraWork`, `createExtraWork`, `updateExtraWork`,
  `completeExtraWork`
- `listDataReview`, `flagShipment`, `bulkFlag`, `purgeTestData`
- `authLogin`, `authLogout`, `authMe`
- `exportExcelUrl`
