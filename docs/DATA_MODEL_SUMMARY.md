# Data Model Summary

_Generated: 2026-05-03 — point-in-time snapshot._

This document describes the SQL tables, their key columns, the
relationships between them, and the current row counts in the live
SQLite DB at `backend/data/royal_linen.db`.

## Tables in DB (15)

```
alerts
containers
document_assignment_actions
document_assignment_qc_results
document_assignment_rules
email_attachments
email_updates
extra_work_tasks
import_batches
pending_containers
pending_document_updates
pending_shipments
shipment_events
shipments
users
```

---

## `shipments` (80 columns) — 34 rows (16 active, 18 archived)

The central table. One row per import shipment.

### Identity
- `id` (PK), `shp_id` (unique, e.g. `SHP-006`, `JOB-28060`)

### Business fields
- `supplier`, `goods_description`, `origin_country`, `origin_port`,
  `shipping_channel` (sea/air/other)
- `current_stage` (1–9), `stage_status`
- Dates: `order_date`, `created_date`, `etd`, `eta_israel`,
  `eta_port`, `eta_warehouse`, `actual_arrival_*`,
  `days_to_arrival`
- IDs: `customs_broker`, `booking_number`, `bol_number`,
  `invoice_number`, `po_number`
- Money: `freight_price_usd`, `goods_value_usd`
- Status flags: `paperwork_complete`, `approval_status`,
  `delay_status`, `delay_reason`, `notes`

### Lifecycle
- `creation_source` (manual / email_import / excel_import /
  excel_import_external)
- `data_source` (demo / manual / excel / email / imported)
- `is_test_data` — bulk-delete uses this flag to safely purge demos
- `archived` (bool), `completed_at`
- `created_at`, `updated_at`, `updated_by`, `last_update_source`

### Manual override metadata
- `manual_overrides` (JSON):
  `{ "eta_israel": {"by": "alice", "at": "..."}, ... }`
- Auto-apply skips any field listed here.

### Categories
- `category`, `category_source` (manual / email_auto / inferred)

### Extra-work fields
- `extra_work_required`, `extra_work_note`,
  `extra_work_defined_at`, `extra_work_defined_by`

### Product image
- `product_image_path` (relative to `uploads/`)

### Email integration provenance
- `source_email_id`, `last_auto_update_source_email_id`,
  `last_auto_update_at`

### External-format import provenance (28 columns added during
external-import work)
- `import_batch_id` (→ `import_batches.id`)
- `source_provider` (`ICL` / `Eli Line` / `Royal Linen Template`)
- `source_file_name`, `source_sheet_name`, `source_row_number`
- `raw_source_json` (full preview row, kept for audit)
- `external_file_number`, `external_job_number`, `sho_list`,
  `customs_file_number`, `house_bill_of_lading_number`,
  `master_bill_of_lading_number`, `vessel_name`, `marks`,
  `incoterm`, `carrier`, `destination_port`,
  `product_description_raw`
- `inferred_brand`, `inferred_category`, `inference_confidence`
- `container_quantity`, `container_quantity_raw`,
  `container_quantity_confidence`, `container_type_raw`,
  `container_raw`, `cbm_raw`
- `needs_review`, `review_reason`

### Relationships
- `1:N` → `containers`
- `1:N` → `extra_work_tasks`
- `1:N` (logical) → `email_attachments` via `linked_shipment_id`

### Current snapshot (post full operational reset, 2026-05-03 20:17:52)
- **shipments table = 0 rows** (active or archived).
- Pre-reset state (34 shipments + 25 containers + 42 documents + 310
  events + 50 alerts + 13 batches + 46 QC results + 39 QC actions +
  3 pending shipments) is preserved in the DB backup at
  `backend/data/backups/royal_linen_before_full_reset_20260503_201752.db`
  and in `backend/exports/full_reset_audit_20260503_201752.xlsx`.

---

## `containers` (45 columns) — 25 rows

One row per physical container. `shipment_id` (FK → `shipments.id`).

### Key columns
- `container_number` (NULL for placeholders), `container_type`
  (`40HC` / `40HQ` / `20'`)
- `cbm`, `boxes_total`, `gross_weight_kg`
- `container_status`
- ETAs: `eta_israel`, `eta_port`, `eta_warehouse`,
  `actual_arrival_*`
- `warehouse_readiness_status`
- `unloading_priority` (`רגיל` / `גבוה` / `דחוף`)
- `extra_work_required`, `extra_work_note`
- Carton dimensions: `carton_length_cm`, `carton_width_cm`,
  `carton_height_cm`
- Pallet calc: `pallet_type_preference`, `estimated_pallets_euro`,
  `estimated_pallets_industrial`, `recommended_pallet_type`,
  `estimated_pallets_final`, `pallet_calc_notes`
- Per-container category override (falls back to shipment's)
- Receiving (Stage 8): `received_cartons_actual`,
  `received_pallets_actual`, `received_notes`, `received_by`,
  `received_at`, `receiving_status` (`not_received` /
  `partially_received` / `received` / `discrepancy`)
- `manual_overrides` (JSON, same shape as on `shipments`)

### Placeholder support (external-format imports)
- `placeholder_container` (bool)
- `actual_container_number_missing` (bool)
- `container_sequence`, `container_raw`, `import_batch_id`,
  `source_row_number`

### Current snapshot (post full operational reset, 2026-05-03 20:17:52)
- **containers table = 0 rows.** Full pre-reset state preserved in
  the backup `.db` and audit `.xlsx`.

---

## `email_updates` — 40 rows

One row per inbound email parsed by the email pipeline (Gmail or
manual upload).

### Key columns
- `email_message_id` (unique), `email_thread_id`
- `sender`, `subject`, `received_at`
- `body_excerpt`, `full_body_text`, `attachment_names` (JSON)
- `detected_shipment_id`, `detected_container_id`
- `confidence_score`, `detected_fields_json`
- `detection_type` ∈ `update_existing` / `new_shipment` /
  `needs_review` / `irrelevant`
- `status` ∈ `pending` / `approved` / `rejected` / `needs_review` /
  `auto_applied` / `ignored` / `assigned`
- Approval/rejection metadata
- Auto-apply: `auto_applied`, `needs_review`, `review_reason`,
  `applied_fields_json`, `flagged_fields_json`

### Status snapshot
- 9 approved, 17 ignored, 6 needs_review, 4 manual_upload,
  3 pending, 1 parsed.

---

## `email_attachments` — 42 rows (1 archived, 10 noise)

The unified document store. Used for both Gmail-fetched files and
manually uploaded files.

### Key columns
- `email_update_id` (FK → `email_updates.id`)
- `filename`, `file_type`, `file_size`, `file_path` (on disk)
- `document_type` (legacy free-form)
- Source IDs: `gmail_attachment_id`, `drive_file_id`, `source_url`
- PDF parsing: `extracted_text`, `text_extraction_status`,
  `parsed_fields_json`
- Links: `linked_shipment_id`, `linked_container_id`
- Soft archive: `archived`, `archived_at`, `archived_by`,
  `archived_reason`, `archived_mode`
  (`archive_record_only` / `archive_file` / `delete_file`)

### Document Intelligence
- `classification` ∈
  - `shipment_document` (generic, catch-all valid)
  - `commercial_invoice`
  - `packing_list`
  - `bill_of_lading` (generic BL)
  - `house_bill_of_lading`
  - `master_bill_of_lading`
  - `purchase_order`
  - `customs_document`
  - `delivery_note`
  - `certificate`
  - `product_image`
  - `email_noise` (logos, signatures, footer images)
  - `unknown_needs_review`
- `classification_confidence` (0..1)
- `classification_reason` (free text — explainability)
- `classified_at`
- `is_email_noise` (bool, in addition to classification, so
  filtering can be cheap)
- `is_inline`, `width_px`, `height_px`
- Field extraction: `extraction_status` ∈ `not_attempted` /
  `pending` / `done` / `text_unavailable` / `error`,
  `extracted_fields_json`
- Manual classification: `manually_classified_by`,
  `manually_classified_at`

### Current classification breakdown
| Classification | Count |
| --- | --- |
| `shipment_document` | 3 |
| `commercial_invoice` | 4 |
| `packing_list` | 3 |
| `bill_of_lading` | 1 |
| `house_bill_of_lading` | 6 |
| `purchase_order` | 14 |
| `email_noise` | 10 |
| (unset) | 1 |

---

## `pending_shipments` — (count not directly inspected; UI
expects single-digit values)

Detected new-shipment proposals from inbound emails. Approved →
creates a real `shipments` row.

### Key columns
- `source_email_update_id`
- `detected_*` mirrors of every shipment field
- `confidence_score`, `missing_fields_json`,
  `detected_fields_json`
- `status` ∈ `pending` / `approved` / `rejected` /
  `assigned_to_existing`
- `assigned_shipment_id` (when assigned to an existing shipment
  rather than creating a new one)
- `1:N` → `pending_containers`

---

## `pending_containers`

`detected_*` mirrors of every container field. Lives under a
`pending_shipment_id` and is materialised when the parent is
approved.

---

## `pending_document_updates`

Field-update suggestions extracted from documents (e.g. an invoice
file says ETA = X, but the shipment has Y). Never auto-applies; the
user must approve.

### Key columns
- `document_id`, `shipment_id`
- `field_name`, `current_value`, `suggested_value`
- `confidence_score`, `reason`
- `status` ∈ `pending` / `approved` / `rejected` / `edited` /
  `superseded`

---

## `extra_work_tasks`

Per-shipment extra-work tasks (sticker change, repacking, vendor
rework). `shipment_id` (FK), optional `container_id` (FK).

### Key columns
- `work_type`, `work_description`, `responsible_party`,
  `external_supplier_name`
- `work_status` (default `לא התחיל`)
- Dates: `expected_start_date`, `actual_start_date`,
  `expected_end_date`, `actual_end_date`,
  `ready_for_distribution_estimated_date`,
  `ready_for_distribution_actual_date`,
  `branch_entry_eta`, `branch_entry_actual_date`
- `delay_status`, `delay_reason`
- `notes`

---

## `shipment_events` — 294 rows

Append-only audit log. One row per write to a tracked field on a
shipment, container, email_update, pending_shipment, or extra_work
task.

### Key columns
- `entity_type` ∈ `shipment` / `container` / `extra_work` /
  `email_update` / `pending_shipment`
- `entity_id`
- `action_type` (e.g. `update`, `create`, `approve`, `archive`)
- `field_changed`, `old_value`, `new_value`
- `changed_by`, `changed_at` (indexed), `source` (manual /
  email_import / system)
- `note`

---

## `alerts` — 50 rows

Generated by `services/alert_service.py`. The hourly scan
deduplicates so each (alert_type, target) does not pile up.

### Key columns
- `alert_type` (e.g. `missing_document_invoice`, `eta_changed_eta_israel`,
  `email_update_needs_review`, `paperwork_missing_late_stage`,
  `receiving_carton_discrepancy`, `pending_shipment_awaiting_approval`,
  `delay_detected_in_email`, `email_update_awaiting_approval`)
- `severity` ∈ `low` / `medium` / `high` / `critical`
- One of `shipment_id` / `container_id` /
  `extra_work_task_id` / `email_update_id` /
  `pending_shipment_id`
- `title`, `description`, `due_date`
- `resolved`, `resolved_by`, `resolved_at`

### Currently unresolved (per scan)
| alert_type | severity | count |
| --- | --- | --- |
| `email_update_awaiting_approval` | high | 6 |
| `email_update_awaiting_approval` | medium | 5 |
| `paperwork_missing_late_stage` | high | 6 |
| `missing_document_invoice` | medium | 6 |
| `missing_document_bl` | medium | 6 |
| `missing_document_packing_list` | medium | 5 |
| `eta_changed_eta_israel` | high | 4 |
| `email_update_needs_review` | high | 4 |
| `delay_detected_in_email` | high | 3 |
| `pending_shipment_awaiting_approval` | high | 3 |
| `receiving_carton_discrepancy` | high | 2 |

---

## `users` — 21 rows

### Key columns
- `username` (unique), `password_hash` (bcrypt)
- `full_name` (new) + legacy `name`
- `phone`, `email`
- `role` ∈ `admin` / `import_manager` / `warehouse` / `viewer`
- `is_active` (new) + legacy `active` (compat)
- `must_change_password` (forces redirect on first login)
- `last_login_at`
- `created_at`, `updated_at`

---

## `document_assignment_qc_results` — 46 rows

One row per (document_id, scan_run) — the latest scan's verdict.

### Key columns
- `document_id` (logical FK to `email_attachments.id`)
- `current_shipment_id`, `suspected_shipment_id`
- `confidence_score` (0–100)
- `severity` ∈ `ok` / `minor` / `suspicious` / `strong_mismatch`
- `status` ∈ `open` / `approved_keep` / `approved_move` /
  `approved_detach` / `dismissed_false_positive` / `ignored` /
  `superseded`
- `mismatch_reasons_json`, `matched_signals_json`
- `recommendation` ∈ `keep` / `review` / `reassign_suggested` /
  `detach_suggested`
- Resolution metadata

### Status snapshot
| status | count |
| --- | --- |
| `approved_move` | 33 |
| `open` | 8 |
| `approved_detach` | 3 |
| `approved_keep` | 2 |

---

## `document_assignment_actions` — 39 rows

Audit log of every approved QC action. Created **only** when the
user explicitly approves a QC suggestion.

### Key columns
- `document_id`
- `old_shipment_id`, `new_shipment_id`
- `action` ∈ `keep` / `move` / `detach` / `mark_correct` /
  `ignore`
- `reason`, `approved_by`, `approved_at`
- `qc_result_id` (link back to the QC result that triggered it)
- `before_json`, `after_json` (the document's link state before
  and after — enables manual revert)

---

## `document_assignment_rules`

Configurable supplier/brand keyword rules used by the QC engine.
Seeded at startup via `seed_builtin_rules`.

### Key columns
- `rule_name`, `supplier_or_brand` (canonical)
- `keywords_json` (list of case-insensitive keywords)
- `active`, `notes`
- `created_by`, `created_at`, `updated_at`

---

## `import_batches` — 13 rows

One row per Excel apply (external formats — ICL / Eli Line — and
optionally Royal Linen Template).

### Key columns
- `source_provider`, `source_file_name`, `source_sheet_name`
- `imported_by`, `imported_at`
- Counters: `total_rows_in_preview`, `created_count`,
  `updated_count`, `skipped_count`, `error_count`
- Rollback metadata: `rolled_back_at`, `rolled_back_by`,
  `rolled_back_reason`, `rolled_back_count`
- `status` ∈ `applied` / `partially_rolled_back` / `rolled_back`
- `notes`, `details_json` (per-row create/update/skip detail for
  full audit + rollback eligibility)

### Snapshot (post-cleanup, 2026-05-03 16:18 UTC)
- 11 of 13 batches are `rolled_back`, 2 are `applied` with 0 created
  (no-op QA batches).
- The 16 JOB-* shipments that were created via the legacy
  `excel_import` path (not `excel_import_external`) were soft-archived
  manually — they had no `import_batch_id` so batch rollback did not
  apply to them. The next real import will go through the new
  external path and produce a proper `import_batches` row.

---

## Logical relationships diagram (text)

```
users
  ↑  (changed_by, etc — by name/string)
  │
shipments  ─────1:N──→ containers
  │                       │
  │                       ↓
  │                    extra_work_tasks
  │
  │   (linked_shipment_id, linked_container_id)
  ↓
email_attachments  ─N:1→ email_updates
  ↑                          │
  │                          ↓ (source_email_update_id)
  │                       pending_shipments  ─1:N→ pending_containers
  │
  │  (document_id)
  ↓
document_assignment_qc_results
document_assignment_actions
pending_document_updates

shipments  ─FK→ import_batches  (via shipments.import_batch_id)
containers ─FK→ import_batches  (via containers.import_batch_id)

shipment_events  (entity_type, entity_id) — points to any of the above

alerts  (shipment_id, container_id, extra_work_task_id, email_update_id,
         pending_shipment_id) — points to whichever applies
```

---

## Conventions worth knowing

- **No hard deletes.** Archived shipments stay (`archived=true`).
  Archived attachments stay (`archived=true`). Containers within an
  archived shipment are reachable but not displayed by default.
- **All datetimes are UTC** in the DB (`datetime.utcnow`). The UI
  formats them in Asia/Jerusalem.
- **manual_overrides** is the single source of truth for "human
  touched this field" — both shipment and container have it.
- **needs_review** flag exists on shipments (created during external
  import when data is incomplete or contradictory) AND on
  email_updates (created when an auto-apply would have overwritten
  a manual override).
- **Tracked fields** are defined in
  `services/shipment_service.py:SHIPMENT_TRACKED_FIELDS` —
  changes outside this set don't generate audit rows.
