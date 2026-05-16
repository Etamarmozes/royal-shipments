# Manual QA Checklist

_Generated: 2026-05-03._

A walk-through checklist a human can run against a fresh deployment
or a recently-changed branch. Tick boxes as you go. Each section is
independent — you can skip and come back.

Browser: any modern Chrome/Edge/Safari/Firefox. Use a private/
incognito window so cached tokens don't hide bugs.

---

## 0. Pre-flight (backend + frontend up)

- [ ] Backend reachable: `GET http://localhost:8000/health` returns
      `{"status":"ok"}`.
- [ ] Backend OpenAPI loads: `http://localhost:8000/docs`.
- [ ] Frontend reachable: `http://localhost:5173/` redirects to
      `/login` (when no token).
- [ ] Health check script passes:
      `python backend/scripts/check_app_health.py` → 8/8 green.

---

## 1. Login + RBAC

- [ ] Open `/login` in incognito window. Hebrew layout (RTL),
      clear labels.
- [ ] Login with `admin / 123456`. If first login, you are
      redirected to `/change-password` and cannot navigate
      elsewhere until you change.
- [ ] Change to a new password (≥ 4 chars). You land on `/`.
- [ ] Logout. Refresh. You're redirected to `/login`.
- [ ] Login again with the new password. Successful.
- [ ] Login with wrong password — clear Hebrew error, no app crash.
- [ ] Try to navigate directly to `/users` as a non-admin (e.g.
      `import_manager`) — you are redirected to `/`.

### Sidebar visibility per role

- [ ] As `admin`: see all 17 nav items.
- [ ] As `import_manager`: see all except `משתמשים והרשאות`.
- [ ] As `warehouse`: see only the read-only set + receiving;
      no `/email-updates`, `/pending-shipments`, `/import-excel`,
      `/import-batches`, `/data-review`, `/document-review`.
- [ ] As `viewer`: same as warehouse but no receiving / upload
      buttons.

---

## 2. Shipments — list + view

- [ ] Open `/shipments`. List loads. **0 shipments visible** after
      the 2026-05-03 20:17:52 full operational reset. Adjust if a
      real import has happened since.
- [ ] Search filter works (e.g. type "Life" — see only LIFE TIME
      shipments).
- [ ] Filter by `current_stage` works.
- [ ] Toggle to show archived → 18 archived show.
- [ ] Click into one shipment. Profile loads. Header shows SHP/JOB
      id, supplier, stage badge.

### Edit a field

- [ ] Edit `eta_israel` to a new date. Save.
- [ ] Banner shows save success.
- [ ] Refresh the page — the new value persists.
- [ ] Look at events history — there's a row for the change with
      old → new value, your username, and timestamp.
- [ ] The 🔒 icon now shows next to `eta_israel` (manual override
      recorded).

### Don't auto-overwrite manual edit

- [ ] (If Gmail is connected:) Send / inject an email update that
      would change `eta_israel` again. Confirm:
  - The shipment's `eta_israel` is **not** auto-updated.
  - An alert appears: "email_update_needs_review".
  - The email update lists `flagged_fields_json: ["eta_israel"]`.

---

## 3. Containers + pallet calc

- [ ] Open `/containers`. List loads.
- [ ] Click into one container. Profile shows.
- [ ] Enter `carton_length_cm`, `carton_width_cm`,
      `carton_height_cm`. Click "חשב משטחים".
- [ ] Both Euro and Industrial breakdowns appear, with cartons-per-
      layer, layers, total height, pallets needed.
- [ ] `recommended_pallet_type` matches whichever breakdown uses
      fewer pallets.

---

## 4. Documents — upload + classify + reassign + archive

### Upload

- [ ] Open `/documents`. Click "העלאה". Pick a PDF that is a real
      packing list (filename includes "PL" or "Packing").
- [ ] Upload succeeds. Document appears in the list.
- [ ] Classification badge says "Packing List" (or its Hebrew
      equivalent).

### Classify-all

- [ ] Click "סווג מחדש את כל המסמכים" (or equivalent button).
      Endpoint runs. Counts update.

### Filter to noise

- [ ] Click the "🚫 רעש מייל" filter. The 10 currently-noise files
      appear.
- [ ] On any one of them, click "Restore as document". Classification
      changes; it disappears from the noise filter.

### Manual reclassify

- [ ] On a misclassified document, click `⋯` → choose a different
      type. Save.
- [ ] The 🔒 icon appears (manual override). Refresh — sticky.

### Reassign

- [ ] Click `שייך` on a document. Search modal opens.
- [ ] Type a supplier name. Top-3 candidate shipments appear.
- [ ] Pick one. Confirm. The document's `linked_shipment_id`
      changes; both the old and new shipment lists reflect the move.

### Archive

- [ ] Click `ארכב` on a document.
- [ ] In the modal, choose `archive_record_only`. Confirm.
- [ ] The document disappears from the default list. Toggle
      "include archived" — it reappears.
- [ ] On a copy, choose `archive_file`. The on-disk file gets
      removed but the row remains (with `archived_mode=archive_file`).
- [ ] On another copy, choose `delete_file`. The modal requires
      typing "DELETE". Type it. Confirm. Row archived,
      file deleted.

---

## 5. Document Assignment QC

- [ ] Open `/document-review` as admin or import_manager.
- [ ] List of "open" QC results appears (currently 8 open per
      snapshot).
- [ ] Each row shows: filename, current shipment, suspected
      shipment, score, reason badges.

### Per-row actions

- [ ] Click `הצג` — preview opens.
- [ ] Click `הורד` — file downloads.
- [ ] Click `שייך` — reassign modal opens with the suspected
      shipment pre-selected.
- [ ] Pick a different shipment (not the suspected one). Confirm.
      Status changes from `open` to `approved_move`.
- [ ] On another row, click `נתק`. Confirm. Status →
      `approved_detach`. Document's `linked_shipment_id` becomes
      NULL.
- [ ] On another row, click `✓ תקין`. Status → `approved_keep`.
- [ ] On another row, click `☐ לבדיקה`. Stays `open` but a
      "marked for later" indicator appears.
- [ ] On another row, click `ארכב`. Same archive modal as
      `/documents`.

### Audit row

- [ ] Inspect `document_assignment_actions` table — every
      approve creates a new row with old/new shipment id,
      `before_json`, `after_json`, your username,
      `qc_result_id` linked.

### Bulk

- [ ] Multi-select 2 rows. Apply the same action to both. Both
      get audit rows.

---

## 6. Excel import — Royal Linen Template

- [ ] As admin/import_manager, open `/import-excel`.
- [ ] Click "הורד תבנית". The Royal Linen template `.xlsx`
      downloads.
- [ ] Open the template, fill in 1-2 fake shipments + 1 container
      each.
- [ ] Save and re-upload.
- [ ] Format detection identifies it as Royal Linen Template.
- [ ] All rows show `_match_level: no_match` (since these are new
      SHP-* ids).
- [ ] Apply with `confirm: APPLY`. Reads "X created, 0 updated,
      0 skipped".
- [ ] New shipments appear in `/shipments` with
      `creation_source=excel_import` (NOT `excel_import_external`).

---

## 7. Excel import — ICL (or Eli Line) external format

Use the real ICL or Eli Line workbook the user wants to import.

- [ ] Drop the file into `/import-excel`.
- [ ] Format auto-detected as `icl` or `eli_line`.
- [ ] Per-row dedup match-level badges show:
  - Red for any rows whose `shipment_reference` already exists.
  - Orange for high-similarity rows.
  - Yellow for soft matches.
  - Empty for genuinely new rows.
- [ ] For a red row, the action defaults to `update`. Try changing
      it to `create` — a "CREATE ANYWAY" modal appears asking you
      to type the literal phrase.
- [ ] Type "CREATE ANYWAY". The row's `_force_create=true` is set.
- [ ] For a yellow row, action defaults to `create` but shows a
      warning about possible match.
- [ ] Apply with `confirm: APPLY`. Server returns counts.
- [ ] In `/import-batches`, the new batch appears with
      `created_count` matching what you applied.
- [ ] Click into the batch. `live_shipments` lists everything
      created. Each row's `had_post_import_edits=false` until the
      first manual edit.

### Server-side safety gate

- [ ] In a fresh import, mark a `red` row as `create` WITHOUT
      typing "CREATE ANYWAY". Server returns 400 with Hebrew
      message + `unsafe_rows` list. UI shows a clear error.

### Rollback

- [ ] Open the batch. Click "Rollback". Modal requires typing
      "ROLLBACK". Type it. Confirm.
- [ ] All shipments created by that batch are now archived.
- [ ] Their containers move with them (cascade).
- [ ] Audit log shows the archive event. The batch status changes
      to `rolled_back`.

---

## 8. Pending shipments + email updates

(Skip if Gmail is not connected. Otherwise:)

- [ ] As admin, open `/email-updates`. Click "סנכרון מ-Gmail".
- [ ] Recently fetched email rows appear.
- [ ] Pick one with `detection_type=update_existing`. Approve. The
      target shipment is updated. Audit log records the source as
      `email_import`.
- [ ] Pick one with `detection_type=new_shipment`. It also
      surfaces in `/pending-shipments`. Approve there. A new
      shipment is created.
- [ ] Inject a synthetic email update via `/email/inject` body
      (use API or admin tool) and confirm it lands in the queue
      with the correct detection_type.

---

## 9. Receiving (warehouse)

- [ ] Login as a `warehouse` user (create one in `/users` first
      if needed). Confirm the sidebar shows only the read-only
      set + `/receiving`.
- [ ] Open `/receiving`. The container queue is ordered by
      warehouse ETA.
- [ ] Click into a container. The full view shows shipment context
      + linked documents.
- [ ] Enter actual cartons received + actual pallets + a note.
      Choose `partially_received` / `received` / `discrepancy`.
- [ ] Save. Confirm the `received_by` is YOUR username (warehouse
      cannot impersonate someone else, even if the request body
      claims another `received_by`).
- [ ] Audit log entry appears.

---

## 10. Extra-work tasks

- [ ] Open `/extra-work`. Create a task: pick a shipment, work_type
      = "החלפת מדבקות", expected_start_date.
- [ ] Save. Task appears in the list.
- [ ] Edit it. Mark complete. Mark delayed.
- [ ] Audit log shows the changes.

---

## 11. Alerts

- [ ] Open `/alerts`. Active alerts visible (currently 50 in DB,
      mix of severities).
- [ ] Click "סריקה ידנית" → triggers the alert scan. Counts
      update.
- [ ] Resolve one alert. It disappears from the active list.

---

## 12. AI assistant

- [ ] On any shipment's profile page, open the AI panel.
- [ ] Click a suggested chip ("האם הניירת מלאה?").
- [ ] Get a structured answer with intent, confidence, sources
      (linked back to the source shipment / container / document).
- [ ] No external API calls (this is rule-based — verify by
      pulling the network tab; only `/ai/ask` should be hit).

---

## 13. History / events

- [ ] Open `/history`. Recent events list.
- [ ] Filter by entity type (shipment / container / extra_work).
- [ ] Filter by actor (your username).
- [ ] Filter by date range (last 24h).
- [ ] Click into an event for full old/new value detail.

---

## 14. Mobile / PWA

(Use a real phone or Chrome devtools mobile emulator.)

- [ ] Open `http://<host>:5173/` on mobile.
- [ ] Top-of-page brand bar visible.
- [ ] Bottom nav with 4 quick actions + "עוד".
- [ ] Tap "עוד" → side drawer slides in from the right (RTL).
- [ ] Tap a nav item → drawer closes + page navigates.
- [ ] Install as PWA (browser's "Add to Home Screen").
- [ ] Open the installed app — manifest icon, no browser chrome.
- [ ] Go offline (airplane mode). Open the app. The offline page
      shows.

---

## 15. Production-readiness sanity

(Optional — only if preparing to deploy.)

- [ ] `AUTH_SECRET` env var is set to a real random value (not the
      dev fallback).
- [ ] `is_production()` returns true (verifiable via Python REPL
      or a debug endpoint).
- [ ] `DATABASE_URL` is set to a Postgres URL.
- [ ] `FILE_STORAGE_PATH` is set to durable storage.
- [ ] CORS `CORS_ALLOWED_ORIGINS` set to the real frontend URL.
- [ ] If Gmail is in use: `GMAIL_DISABLED=false` and OAuth
      credentials valid for the deployment domain.
- [ ] If Gmail is NOT in use: `GMAIL_DISABLED=true` so all
      `/gmail/*` cleanly return 503.
- [ ] At least one admin login works besides the bootstrap admin.
- [ ] `EMERGENCY_ADMIN_USERNAME` / `EMERGENCY_ADMIN_PASSWORD` set
      for break-glass.
- [ ] Backup process for `data/royal_linen.db` (or Postgres) +
      `uploads/` is in place.
