# Email Sync — Approval Workflow (planned, not built yet)

> **Status:** Architecture only — to be built in Phase 3+ once the
> Excel import flow is in production use. The Excel flow comes first
> by user request: "Before connecting the email, first create and
> export the Excel shipment import template."

This document describes the **planned** approval-based email sync.
It supersedes the current Gmail integration once built.

---

## Why approval-based, not auto-apply

Today's Gmail integration auto-applies "safe" updates (filling empty
fields, adding new containers) and flags "risky" updates for review.
The new flow makes **everything** a pending update by default — no
shipment field is touched until the user clicks Approve.

Reason: the system is going from "demo + few real shipments" to "many
real shipments imported from Jacob's mailbox." The first few weeks
need a human in the loop to build trust in the matcher.

---

## Provider architecture

```
EmailProvider (interface)
├── GmailProvider          — current Gmail OAuth implementation
├── MicrosoftGraphProvider — placeholder for future M365 migration
└── ManualEmailImportProvider — paste/upload .eml or .msg files
```

Each provider implements:
- `connect()` — OAuth or credentials
- `disconnect()` — revoke
- `list_messages(filters)` — return ProviderMessage objects
- `download_attachment(message_id, attachment_id)` — bytes

Filters (uniform across providers):
- mailbox
- date range (default last 90 days for first sync)
- sender allowlist
- subject/body keywords
- attachment-only flag
- unread/all
- folder/label (Gmail labels, Outlook folders)

---

## Pending Email Updates screen

`/pending-email-updates`

For each pending email update, show:
1. Original email subject
2. Sender + recipients
3. Email date
4. Body preview (200 chars)
5. Attachments (with preview/download)
6. **Extracted fields** (parser output):
   - supplier, forwarder, shipment_reference
   - PO, invoice, packing list, BL
   - container, vessel, ports
   - ETD, eta_port, eta_warehouse, delivery_date
   - customs/warehouse status
7. Confidence score (0.0–1.0)
8. Matched shipment/container (if any)
9. Suggested action:
   - `create_new_shipment`
   - `update_existing_shipment`
   - `attach_document_only`
   - `ignore`
10. Buttons: **Approve** / **Reject** / **Edit before approval**

Only after user clicks Approve does the shipment data change.

---

## Confidence levels

| Level | Trigger | Default action |
|---|---|---|
| **High** (≥0.85) | Exact container_number / BL / shipment_reference match | Pre-fill update form, user confirms |
| **Medium** (0.5–0.84) | supplier + PO/invoice + date proximity | Show as "Suggested match" — user picks |
| **Low** (<0.5) | Only supplier or vague text | Mark "Needs Review", no auto-suggestion |

Low-confidence emails go to a separate "Needs Review" tab so they don't
clutter the main pending list.

---

## Sync log table (planned)

```sql
CREATE TABLE email_sync_log (
  id INTEGER PRIMARY KEY,
  provider TEXT,             -- 'gmail' / 'graph' / 'manual'
  mailbox TEXT,              -- 'jacobg@royal-linen.com'
  message_id TEXT UNIQUE,
  thread_id TEXT,
  synced_at DATETIME,
  sender TEXT,
  subject TEXT,
  attachments_count INTEGER,
  extracted_fields_json TEXT,
  matched_shipment_id INTEGER,
  confidence_score REAL,
  action_taken TEXT,         -- 'pending_review' / 'approved' / 'rejected' / 'auto_applied'
  approved_by TEXT,
  approved_at DATETIME,
  rejected_reason TEXT
);
```

Surfaced in `/data-source-status` page so the operator can see:
- Last sync time per provider
- # pending / # failed / # approved today
- Connection status

---

## Keyword-based pre-filter

Only emails matching shipment-related keywords are pulled into the
review queue (rest are ignored):

**English:** shipment, container, ETA, ETD, BL, bill of lading,
invoice, packing list, customs, clearance, delivery, warehouse, port,
vessel, sailing, arrival, DHL, Maersk, ZIM, MSC, forwarder, supplier

**Hebrew:** משלוח, קונטיינר, מכולה, חשבונית, אריזה, שטר מטען,
עמיל מכס, שחרור, נמל, מחסן, הגעה, אספקה, מסמכים

Senders can also be allowlisted (e.g. `*@maersk.com`, `*@dhl.com`,
forwarder emails) — those bypass the keyword check.

---

## Safe first-sync workflow (planned)

1. Operator opens `/email-sync-settings`
2. Selects mailbox: `jacobg@royal-linen.com`
3. Sets date range: **last 90 days** (default — never "all")
4. Picks providers' OAuth flow
5. Clicks "Test sync (preview only, no save)"
6. System pulls + extracts but writes only to `email_sync_log` with
   `action_taken='pending_review'`
7. Operator reviews `/pending-email-updates`
8. Approves/rejects each one
9. Once comfortable, enables "scheduled sync (hourly)" with the same
   filters and an automatic-approve threshold (default: never auto-approve)

This is the workflow we're not building yet — but the data model
(`email_updates`, `email_attachments`, `manual_overrides`) already
supports it. The remaining work is:
- New router `/pending-email-updates`
- New service `email_extractor_service` (replaces auto-apply)
- New page `/pending-email-updates` and `/email-sync-settings`
- `provider_factory.py` with the 3 providers

---

## What works today

The CURRENT Gmail integration still works — it's just auto-apply
oriented. Until the new approval flow ships:

- `/gmail/sync` pulls emails and runs the existing classifier
- "Safe" updates auto-apply (e.g. filling empty ETA when shipment
  has none)
- "Risky" updates create alerts and are flagged in `/email-updates`
- Manual overrides are sticky (covered in
  [`SHIPMENT_DATA_IMPORT.md`](./SHIPMENT_DATA_IMPORT.md))

If you need a hard kill-switch:
```
GMAIL_DISABLED=true   # in backend/.env
```
See [`GOOGLE_DEPENDENCIES.md`](../GOOGLE_DEPENDENCIES.md).

---

## Migration to Microsoft 365 (future)

When/if the org moves from Google Workspace to M365:

1. Implement `MicrosoftGraphProvider` (OAuth via Azure app
   registration, scope `Mail.Read`)
2. Add `EMAIL_PROVIDER=graph` env var
3. Migrate the OAuth callback URL in Azure
4. Existing `email_updates` rows continue to work — only the
   provider changes

No data migration needed; provider is just the source.
