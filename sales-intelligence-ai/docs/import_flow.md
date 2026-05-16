# Import flow

How a file in `data/comax_reports/` becomes rows in the database.

## Trigger

One of:

1. **Manual** — user clicks "Run import" on the Imports page → `POST /imports/run`.
2. **Scheduled** — APScheduler job runs every `WATCHER_INTERVAL_SECONDS` (default 60s) and processes any new files.
3. **Upload** — user uploads through the UI → `POST /imports/upload` → file lands in `data/comax_reports/` → same pipeline.

## Pipeline

```
                  data/comax_reports/foo.xlsx
                            │
                            ▼
                  ┌─────────────────────┐
                  │ 1. Hash + dedupe    │  SHA-256 vs import_logs.file_hash
                  └─────────┬───────────┘
                            │ (skip if seen)
                            ▼
                  ┌─────────────────────┐
                  │ 2. ExcelParser      │  pandas/polars: list sheets, read all
                  └─────────┬───────────┘
                            ▼
                  ┌─────────────────────┐
                  │ 3. ReportDetector   │  filename + sheet names + columns
                  │                     │  → "sales_by_item" / "inventory" / …
                  └─────────┬───────────┘
                            │ (if unknown → status=failed, prompt user to map)
                            ▼
                  ┌─────────────────────┐
                  │ 4. ColumnNormalizer │  Hebrew + English headers → canonical
                  └─────────┬───────────┘
                            ▼
                  ┌─────────────────────┐
                  │ 5. RowValidator     │  required cols, types, ranges
                  └─────────┬───────────┘
                            ▼
                  ┌─────────────────────┐
                  │ 6. EntityResolver   │  upsert stores/items/brands/categories
                  └─────────┬───────────┘
                            ▼
                  ┌─────────────────────┐
                  │ 7. FactWriter       │  bulk insert sales / inventory
                  └─────────┬───────────┘
                            ▼
                  ┌─────────────────────┐
                  │ 8. ImportLog write  │  status, counts, warnings, errors
                  └─────────┬───────────┘
                            ▼
                ┌─ success ─┴─ failed ─┐
                ▼                       ▼
       data/imported/foo.xlsx   data/failed/foo.xlsx
                                + foo.xlsx.error.json
```

## Report type detection

Order of checks:

1. **Filename hints** (case-insensitive substring match):
   - `sales`, `מכר`, `מכירות` → sales family
   - `inventory`, `מלאי`, `stock` → inventory
   - `item`, `פריט`, `master` → items master
   - `store`, `סניף`, `branch` → stores master
2. **Sheet name hints** (same vocabulary).
3. **Column signature** — a fingerprint of normalized column names. E.g. presence of `quantity` + `gross_sales` + `date` + `store` → `sales_by_item`.

If two signals agree → `confidence=high`. One signal only → `confidence=medium`, file is imported but flagged on the Imports page. No signal → `status=failed, reason="report_type_unknown"`, file moved to `data/failed/`.

## Column normalization

A bilingual dictionary maps source headers to canonical fields. Lookup is case-insensitive, whitespace-stripped, and ignores Hebrew niqqud.

| canonical | accepted source headers |
|---|---|
| `date` | `date`, `תאריך`, `תאריך חשבונית`, `יום` |
| `store_code` | `store`, `סניף`, `קוד סניף`, `מס סניף`, `branch` |
| `store_name` | `store name`, `שם סניף`, `שם הסניף` |
| `item_code` | `item`, `מק״ט`, `מקט`, `קוד פריט`, `sku` |
| `barcode` | `barcode`, `ברקוד`, `EAN`, `UPC` |
| `item_name` | `item name`, `שם פריט`, `תיאור`, `תיאור פריט` |
| `brand` | `brand`, `מותג`, `יצרן` |
| `category` | `category`, `קטגוריה`, `קבוצה`, `מחלקה` |
| `supplier` | `supplier`, `ספק`, `שם ספק` |
| `quantity` | `quantity`, `כמות`, `כמות מכר`, `יחידות` |
| `gross_sales` | `gross sales`, `מכר ברוטו`, `סכום ברוטו` |
| `net_sales` | `net sales`, `מכר נטו`, `סכום נטו` |
| `discount_amount` | `discount`, `הנחה`, `סכום הנחה` |
| `return_quantity` | `returns`, `החזרות`, `כמות זיכוי` |
| `cost_price` | `cost`, `מחיר עלות`, `עלות` |
| `selling_price` | `price`, `מחיר`, `מחיר מכירה` |
| `inventory_quantity` | `stock`, `מלאי`, `כמות במלאי` |
| `available_quantity` | `available`, `זמין`, `מלאי זמין` |
| `on_order_quantity` | `on order`, `בהזמנה`, `הזמנות פתוחות` |

Headers that don't match are preserved in the import log under `warnings.unmapped_columns`.

## Number / date parsing rules

- Currency symbols (`₪`, `$`, `€`) and thousands separators are stripped before parsing.
- Percent values are converted to floats (`12%` → `0.12`).
- Empty cells → NULL, not zero (zero is a real measurement).
- Dates accept: `dd/mm/yyyy`, `yyyy-mm-dd`, `dd-mm-yyyy`, Excel serial.
- All-row date column with mixed formats → row-level flag, file marked `partial`.

## Failure handling

Files moved to `data/failed/` are accompanied by `<original_name>.error.json`:

```json
{
  "file": "מכר לפי פריטים 2026-05-03.xlsx",
  "report_type_guess": "sales_by_item",
  "confidence": "low",
  "reason": "missing_required_columns",
  "missing": ["date"],
  "rows_detected": 1240,
  "imported_at": "2026-05-03T10:14:22Z"
}
```

The Imports page shows these and offers a manual column-mapping screen.

## Idempotency

- `file_hash` (SHA-256 of bytes) is unique. Re-dropping the same file → instant skip.
- Inside a single import, sales rows for the same `(date, store, item)` are upserted (sum if explicitly partial, otherwise treated as a corrected restate — config flag).

## What gets logged

Every run appends to `logs/import.log` and to the `import_logs` table:

```
2026-05-03 10:14:22 INFO  import.start  file=מכר לפי פריטים.xlsx hash=ab12…
2026-05-03 10:14:22 INFO  import.detect type=sales_by_item confidence=high
2026-05-03 10:14:23 INFO  import.normalize unmapped=[הערות]
2026-05-03 10:14:23 WARN  import.validate row=14 col=quantity reason=non_numeric value="abc"
2026-05-03 10:14:24 INFO  import.write   inserted=1239 skipped=1
2026-05-03 10:14:24 INFO  import.done    status=partial duration_ms=1820
```
