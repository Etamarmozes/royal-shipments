# Current Status & Next Steps

_Generated: 2026-05-03 — point-in-time snapshot._

## Post-sync cleanup (2026-05-03 20:39:46)

After the full operational reset finished at 20:17:52, an unintended
Gmail sync (`POST /gmail/sync`) ran ~2.5 minutes later and inserted 19
email_updates + 38 email_attachments + 21 shipment_events + downloaded
38 files into `uploads/documents/`. A targeted cleanup was run via
`backend/scripts/post_sync_cleanup.py --confirm POST_SYNC_CLEANUP`:

| Artifact | Path |
| --- | --- |
| DB backup of post-sync state | `backend/data/backups/royal_linen_before_post_sync_cleanup_20260503_203946.db` |
| Audit Excel of the 19+38+21 rows | `backend/exports/post_sync_cleanup_audit_20260503_203946.xlsx` |
| Log file | `backend/logs/post_sync_cleanup_20260503_203946.log` |
| Files moved (38 items) | `backend/uploads/archive_before_reset/20260503_203946/` |

Kill-switch: `backend/.env` now contains `GMAIL_DISABLED=true`. Once
the backend is restarted, every `/gmail/*` endpoint returns 503,
preventing any future stray button click from re-triggering Gmail
sync. Set `GMAIL_DISABLED=false` (or delete the line) and restart to
re-enable.

`backend/app/config.py` was given a one-line change at the top:
`from dotenv import load_dotenv; load_dotenv(<.env path>, override=False)`
so the .env file is auto-loaded on backend startup. Real OS env vars
still take precedence.

## Full operational reset (2026-05-03 20:17:52)

A controlled full operational reset was run via
`backend/scripts/full_operational_reset.py --confirm FULL_RESET`.
Outputs:

| Artifact | Path |
| --- | --- |
| DB backup (full pre-reset state) | `backend/data/backups/royal_linen_before_full_reset_20260503_201752.db` (~616 KB) |
| Audit Excel (per-table dump of every operational row that existed) | `backend/exports/full_reset_audit_20260503_201752.xlsx` (~118 KB, 13 sheets + summary) |
| Log file | `backend/logs/full_reset_20260503_201752.log` |
| Physical-file archive (43 items) | `backend/uploads/archive_before_reset/20260503_201752/` |

To restore: stop the backend, copy the backup `.db` over
`backend/data/royal_linen.db`, restart the backend, optionally move
the archived files back into `backend/uploads/documents/`.

## Executive snapshot

- **Backend health:** 8/8 health-check passes (per
  `backend/scripts/check_app_health.py`).
- **Frontend build:** clean (998 modules, ~142 KB gzip per most recent
  build during the dev session).
- **Active shipments:** **0** (post **full operational reset** at
  2026-05-03 20:17:52 local time).
- **Archived shipments:** **0**.
- **Containers:** **0**.
- **Documents (`email_attachments`):** **0** (the underlying 43
  files on disk were *moved*, not deleted, to
  `backend/uploads/archive_before_reset/20260503_201752/`).
- **Import batches:** **0**.
- **Audit log (`shipment_events`):** **0** (pre-reset audit is
  preserved inside the backup `.db` and the audit `.xlsx`).
- **Alerts, QC results, QC actions, pending updates, pending
  shipments, extra work tasks, email updates:** all **0**.
- **Preserved:** users (21, including 2 admins), document assignment
  rules (6 supplier/brand rules seeded by the app at startup).
- **Alerts:** 50 total in the table; some resolved + some unresolved
  (counts in DATA_MODEL_SUMMARY).
- **Users:** 21.
- **DB:** SQLite at `backend/data/royal_linen.db`.

---

## What is fully working ✅

These are end-to-end wired and exercised at least once during the
recent dev session.

1. **Authentication + RBAC**
   - bcrypt password hashing, JWT (24h), force-change-on-first-login,
     emergency env-var admin, `/auth/me.permissions` for UI gating.

2. **Shipment CRUD + audit log + manual_overrides**
   - List, search, view, edit, archive (soft).
   - Every tracked-field change generates an event row + a
     `manual_overrides` entry with actor + timestamp.

3. **Container CRUD + pallet calculator**
   - Per-container Euro / Industrial pallet breakdown, daily and
     weekly forecast aggregation.

4. **Documents — unified store + smart status**
   - Upload, download (authenticated), reassign, classify (rule-based,
     15 classes), reclassify-all, mark/restore noise, smart 3-tile
     status panel with recalc.

5. **Document Assignment QC console**
   - Background hourly scan, operational `/document-review` page with
     all 7 action buttons, ReassignModal with shipment search,
     ArchiveModal with 3 modes (record_only / archive_file /
     delete_file requires "DELETE" confirm).
   - 39 audit rows in `document_assignment_actions`.

6. **Excel import — multi-format preview + apply**
   - Auto-detection of Royal Linen Template / ICL / Eli Line.
   - 3-step wizard with dedup match-level badges (red/orange/yellow).
   - 0-100 scoring engine, 4 match levels.
   - "CREATE ANYWAY" force-create modal blocks unsafe creates by
     default.
   - Server-side safety gate re-validates on apply.

7. **Import batches + rollback**
   - Per-batch live-shipments view with `had_post_import_edits` flag.
   - Rollback requires "ROLLBACK" confirmation. Archives only
     external-import shipments. Never reverts UPDATE actions.

8. **Warehouse receiving**
   - Queue ordered by warehouse ETA. Per-container receive form.
     Forces `received_by` to the authenticated user.

9. **Alerts engine**
   - 9 distinct alert types. Hourly background scan. Resolution
     workflow.

10. **Audit / events history page**
    - 294 events filterable by entity / actor / date.

11. **AI assistant (rule-based)**
    - Per-page suggested questions, context-aware structured answers.

12. **Pending shipments + email update queue**
    - Approve / reject / assign-to-existing / edit-before-approve.

13. **Health check script**
    - `backend/scripts/check_app_health.py` — pure stdlib, 8 checks.

---

## What is partially implemented 🟡

1. **Gmail OAuth integration**
   - Backend: ✅ Code is written. OAuth callback, token persistence,
     `/gmail/sync`, `/gmail/disconnect`, kill-switch env var.
   - Frontend: ✅ UI surfaces are present in `/email-updates`.
   - **Caveat:** End-to-end `/gmail/sync` was NOT re-verified during
     the most recent dev session. The focus during that session was
     on Excel import + QC console + cleanup.
   - **Action needed:** Manual run of `/gmail/sync` once Google
     credentials are confirmed working in the deployment
     environment.

2. **Royal Linen Template apply path**
   - Backend: ✅ Code exists (`excel_import_service.apply`).
   - **Caveat:** Only the ICL + Eli Line apply paths were exercised
     end-to-end during the most recent session (with synthetic test
     workbooks). The Royal Linen template apply path was not
     re-verified after the external-format work.
   - **Action needed:** Run the Royal Linen template through the
     `/import-excel` flow once on a test file before relying on it
     in production.

3. **Email auto-apply policy**
   - Backend: ✅ `email_apply_service` respects `manual_overrides`,
     creates `flagged_fields_json` + `needs_review` alerts.
   - **Caveat:** The policy thresholds (which `confidence_score`
     auto-applies vs sends to review) have been tuned against
     synthetic data, not yet against the production Gmail traffic
     volume.

---

## Backend exists, frontend missing 🔵

- **`/email/inject` endpoint** is wired into the frontend (testing
  helper) but is hidden behind the email-updates page; not actively
  exposed in the sidebar. ✅ Acceptable as designed.
- **`/users/:id/reset-password`** is wired in `/users` page.
- I did not find any backend-only-no-frontend gaps during this
  inspection. **Status: none observed.**

---

## Frontend exists, backend missing ⚪

None observed during this inspection.

---

## Planned only / not built 🔴

- **Notifications layer** (push notification, email digest) — out
  of scope for current phase.
- **Multi-warehouse support** — current data model assumes a
  single warehouse.
- **Per-supplier dashboard** — beyond what's already in `/categories`.
- **Customer-facing supplier portal** — `/help/supplier` is a
  reference page only, not an interactive portal.
- **Real-time collaboration** (concurrent-edit conflict
  resolution) — current write-flow is last-writer-wins with audit
  trail.

---

## Things that need verification ❓

| Area | What to verify |
| --- | --- |
| Gmail end-to-end sync | Connect OAuth, run `/gmail/sync`, confirm new emails land in `email_updates` and create alerts. |
| Royal Linen template apply | Use `/import/excel/template` → fill → re-upload → preview → apply. |
| Force-create flow with real exact-duplicate | Confirm UI requires "CREATE ANYWAY" and server allows after `_force_create=true`. |
| Hourly scheduler in production | Confirm APScheduler keeps running for >1 hour; verify alert + QC scans run on schedule. |
| Mobile (real device) | The app is PWA-capable; confirm install + offline page on iOS Safari and Chrome Android. |
| Production-grade `AUTH_SECRET` | Confirm `is_production()` returns true (i.e. dev fallback `AUTH_SECRET` is overridden). |

---

## Main risks (operational)

1. **No Alembic migration history yet for the additive changes.**
   The `add_missing_columns` runner is idempotent and additive-only,
   but if a non-additive change is needed in the future it will
   require either a one-time SQL script or a real Alembic migration
   chain. **Mitigation:** all current schema changes have been
   additive; no DROP / RENAME paths exist.

2. **(Resolved 2026-05-03 16:18 UTC)** The 16 active JOB-* shipments
   that came in via the older `excel_import` creation_source have been
   soft-archived. They are no longer in the active list. The user will
   re-import the same data via the new external path so that
   `import_batch_id` and full provenance metadata are populated and
   future rollbacks work correctly. **Audit trail preserved** — both
   the original `excel_import_create` events and the new `archive`
   events remain in `shipment_events`.

3. **Gmail OAuth credentials.** The credentials.json checked into
   the backend dir is for development. Production deployment needs
   its own OAuth client with the correct redirect URI.
   **Mitigation:** kill-switch env `GMAIL_DISABLED=true` keeps the
   rest of the app up if Gmail is misconfigured.

4. **JWT secret rotation.** Changing `AUTH_SECRET` will invalidate
   every issued token. Plan a maintenance window before changing it
   in production.

5. **Single-DB single-machine.** Currently one SQLite file, one
   uploads/ folder. Production deployment should switch to Postgres
   via `DATABASE_URL` and put `uploads/` on durable storage (S3 or
   mounted volume).

6. **Email-noise classifier coverage.** The classifier successfully
   filtered the 10 known logo / signature files, but a new sender
   format with novel embedded images may not be covered by the
   current keyword + size rules. **Mitigation:** the manual
   classification override (with 🔒 icon) lets users correct
   misclassifications and the system records who corrected them.

---

## Recommended next phases

### Phase A — first real-world import ✅ ready to go

The system is ready for the user to do a first real import of an
ICL / Eli Line Excel file end-to-end:
1. Navigate to `/import-excel`.
2. Upload the file.
3. Review the dedup-match badges; resolve any flagged duplicates.
4. Apply with `confirm: APPLY`.
5. Verify the new shipments appear in `/shipments` with
   `creation_source = excel_import_external` and the right
   `import_batch_id`.
6. If anything is wrong: navigate to `/import-batches` and run
   rollback with `confirm: ROLLBACK`.

### Phase B — connect Gmail (1 day of QA)

1. Confirm Google OAuth credentials are valid for the deployment
   environment.
2. Run `/gmail/connect` flow, complete OAuth.
3. Run `/gmail/sync` manually.
4. Inspect `/email-updates` — confirm received emails appear with
   correct detection_type and confidence.
5. Approve a low-risk email update; confirm shipment is updated and
   audit log shows the change with `source=email_import`.

### Phase C — let the hourly scheduler run for a day

Confirm in production logs that:
- `alert_service.scan_alerts(db)` runs hourly without exception.
- `email_sync_service.sync_now(db)` runs without exception.
- `document_qc_service.run_scan(db)` runs without exception.

### Phase D — deploy with Postgres + persistent uploads

When ready for multi-user production:
1. Switch `DATABASE_URL` to a Postgres URL.
2. Mount `FILE_STORAGE_PATH` on durable storage.
3. Override `AUTH_SECRET` with a real random secret.
4. Set `EMERGENCY_ADMIN_USERNAME` / `EMERGENCY_ADMIN_PASSWORD` for
   break-glass access.
5. Set `GMAIL_DISABLED=true` until OAuth is verified, then flip.

---

## Exact next action

Open `/import-excel` (default URL: `http://localhost:5173/import-excel`)
as the bootstrap admin or any `import_manager` user, drop the next
real ICL or Eli Line Excel file into the dropzone, and walk through
preview → review match badges → apply.

After that import has applied, validate by navigating to:
- `/shipments` — confirm new shipments appear with correct
  `creation_source = excel_import_external`.
- `/import-batches` — confirm a new batch row exists with the
  correct counts (created / updated / skipped).
- `/alerts` — confirm no surprising new alerts (e.g. missing
  documents on the new shipments — those are expected since no
  documents have been linked yet).

---

## What this documentation pass changed

**Nothing in the running system.** This pass was strictly
read-only — inspecting code, database state, and current wiring;
producing the 9 markdown files in `docs/`. No code edits, no DB
writes, no file deletions, no schema changes.
