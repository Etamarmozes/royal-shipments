# Database schema

SQLite for MVP. PostgreSQL-ready: every type, default, and constraint chosen here is portable. Switching is `DATABASE_URL=postgresql://...` and re-running migrations.

## Conventions

- Surrogate `id INTEGER PRIMARY KEY` on every table.
- Natural keys (`store_code`, `barcode`, `item_code`) are `UNIQUE` indexed.
- Money columns are `NUMERIC(14, 2)` (mapped to `Float` on SQLite, `Numeric` on PG).
- Quantities are `NUMERIC(12, 3)` to allow fractional units (kg, m).
- Dates without time are `DATE`. Snapshots and event timestamps are `DATETIME` (UTC).
- Soft-deletes via `active BOOLEAN DEFAULT TRUE` on dimension tables.
- Every fact row carries `source_file_id` → `import_logs.id` for traceability.

## Dimensions

### `stores`
| col | type | notes |
|---|---|---|
| id | INT PK | |
| store_code | TEXT UNIQUE | code from Comax |
| store_name | TEXT | display name |
| region | TEXT | optional |
| store_type | TEXT | "outlet" / "flagship" / "general" / "value" |
| active | BOOL | |

### `brands`
| col | type | notes |
|---|---|---|
| id | INT PK | |
| name | TEXT UNIQUE | |

### `categories`
| col | type | notes |
|---|---|---|
| id | INT PK | |
| name | TEXT UNIQUE | |
| parent_category_id | INT NULL FK→categories.id | hierarchy |

### `suppliers`
| col | type | notes |
|---|---|---|
| id | INT PK | |
| name | TEXT UNIQUE | |

### `items`
| col | type | notes |
|---|---|---|
| id | INT PK | |
| item_code | TEXT UNIQUE | Comax item code |
| barcode | TEXT INDEX | EAN/UPC, may differ from item_code |
| item_name | TEXT | |
| brand_id | INT NULL FK | |
| category_id | INT NULL FK | |
| supplier_id | INT NULL FK | |
| cost_price | NUMERIC(14,2) NULL | last known cost |
| selling_price | NUMERIC(14,2) NULL | list price |
| active | BOOL | |

## Facts

### `sales`
Daily grain: one row per (date, store, item).

| col | type | notes |
|---|---|---|
| id | INT PK | |
| date | DATE INDEX | business date of the sale |
| store_id | INT FK | |
| item_id | INT NULL FK | resolved from barcode/code |
| barcode | TEXT NULL | preserved as-imported |
| quantity | NUMERIC(12,3) | units sold |
| gross_sales | NUMERIC(14,2) | before discount |
| net_sales | NUMERIC(14,2) | after discount, after returns |
| discount_amount | NUMERIC(14,2) DEFAULT 0 | |
| return_quantity | NUMERIC(12,3) DEFAULT 0 | |
| cost_amount | NUMERIC(14,2) NULL | qty × cost |
| gross_margin_amount | NUMERIC(14,2) NULL | net_sales − cost_amount |
| source_file_id | INT FK→import_logs.id | |

Indexes: `(date, store_id)`, `(date, item_id)`, `(store_id, item_id, date)`.

### `inventory_snapshots`
One row per (snapshot_date, store, item).

| col | type |
|---|---|
| id | INT PK |
| snapshot_date | DATE INDEX |
| store_id | INT FK |
| item_id | INT FK |
| barcode | TEXT NULL |
| inventory_quantity | NUMERIC(12,3) |
| available_quantity | NUMERIC(12,3) NULL |
| on_order_quantity | NUMERIC(12,3) NULL |
| source_file_id | INT FK |

### `purchase_orders`
| col | type |
|---|---|
| id | INT PK |
| order_date | DATE |
| expected_arrival_date | DATE NULL |
| supplier_id | INT FK |
| item_id | INT FK |
| quantity | NUMERIC(12,3) |
| status | TEXT |  ← "open" / "partial" / "received" / "cancelled" |

### `price_history`
| col | type |
|---|---|
| id | INT PK |
| item_id | INT FK |
| store_id | INT NULL FK | NULL = chain-wide |
| price | NUMERIC(14,2) |
| start_date | DATE |
| end_date | DATE NULL |

### `promotions`
| col | type |
|---|---|
| id | INT PK |
| promotion_name | TEXT |
| item_id | INT FK |
| store_id | INT NULL FK |
| start_date | DATE |
| end_date | DATE |
| promotion_price | NUMERIC(14,2) |

## Operational tables

### `import_logs`
Every file ingest produces one row.

| col | type |
|---|---|
| id | INT PK |
| file_name | TEXT |
| original_path | TEXT |
| file_hash | TEXT UNIQUE | SHA-256 — blocks duplicate imports |
| report_type | TEXT | "sales_by_item" / "inventory_by_store" / … |
| status | TEXT | "success" / "partial" / "failed" |
| imported_at | DATETIME |
| data_date_min | DATE NULL |
| data_date_max | DATE NULL |
| rows_detected | INT |
| rows_imported | INT |
| rows_failed | INT |
| warnings | TEXT (JSON) |
| errors | TEXT (JSON) |
| user_notes | TEXT NULL |

### `generated_reports`
| col | type |
|---|---|
| id | INT PK |
| report_type | TEXT |
| title | TEXT |
| file_path | TEXT |
| format | TEXT | "jpg" / "png" / "pdf" / "xlsx" |
| generated_at | DATETIME |
| generated_by | TEXT NULL |
| parameters_json | TEXT |

### `ai_analysis_logs`
| col | type |
|---|---|
| id | INT PK |
| question | TEXT |
| answer | TEXT |
| tools_used | TEXT (JSON list) |
| created_at | DATETIME |
| data_sources_used | TEXT (JSON) |

## Data freshness queries

The dashboard's "data freshness" widget runs:

```sql
SELECT MAX(date) FROM sales;
SELECT MAX(snapshot_date) FROM inventory_snapshots;
SELECT MAX(imported_at) FROM import_logs WHERE status IN ('success','partial');
```

A report type that hasn't been imported in N days surfaces as a dashboard alert.
