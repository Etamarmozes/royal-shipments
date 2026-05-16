# Comax API integration — Phase 2 plan

## Today (Phase 1)

The system reads files from `data/comax_reports/`. The user (or a scheduled script on the Comax PC) drops Excel/CSV exports into that folder.

## Tomorrow (Phase 2)

Comax provides a REST API. The system pulls data directly on a schedule. No file copying. No manual exports.

The transition requires **no changes** to the dashboard, AI, recommendation engine, or reports — only the data source layer is swapped.

## How the swap works

`backend/app/ingestion/data_source.py` defines a single abstract class:

```python
class DataSource(ABC):
    @abstractmethod
    def fetch_sales(self, start_date, end_date) -> Iterable[NormalizedSalesRow]: ...
    @abstractmethod
    def fetch_inventory(self, snapshot_date) -> Iterable[NormalizedInventoryRow]: ...
    @abstractmethod
    def fetch_items(self) -> Iterable[NormalizedItem]: ...
    @abstractmethod
    def fetch_stores(self) -> Iterable[NormalizedStore]: ...
    @abstractmethod
    def fetch_prices(self, store_id=None) -> Iterable[NormalizedPrice]: ...
    @abstractmethod
    def fetch_promotions(self, active_on=None) -> Iterable[NormalizedPromotion]: ...
```

Phase 1 implementation: `FileDataSource(folder=...)` — yields rows by walking the folder.

Phase 2 implementation: `ComaxApiDataSource(base_url, auth, ...)` — yields rows from API responses.

Switching is a single config flag in `.env`:

```
DATA_SOURCE=file        # Phase 1
DATA_SOURCE=comax_api   # Phase 2
```

## What we need from Comax (collect this in advance)

To save time when access is granted, request the following from your Comax representative:

### Credentials & access
- API base URL (production and sandbox)
- Authentication method: API key? OAuth client credentials? Basic auth + token endpoint?
- Rate limits (req/sec, daily quota)
- IP allowlist requirement?
- TLS / certificate requirements

### Endpoints we need
- Sales — daily granularity, filterable by date range and store
- Inventory snapshot — current and historical if available
- Items master — code, barcode, name, brand, category, supplier, cost, list price
- Stores master
- Price list / price changes
- Promotions
- Purchase orders (status + ETA)
- Returns / cancellations

For each endpoint, we need:
- Exact path and HTTP verb
- Request parameters (paging, filters)
- Response schema (sample JSON)
- Pagination model (cursor / offset / page-size limits)
- Incremental sync support (`updated_since`?) — critical for not re-pulling history every night

### Data modeling
- Are barcodes globally unique? Or per-supplier?
- Multi-store inventory: does the API return per-store, or do we have to call once per store?
- How are returns represented? Negative quantity in sales? A separate endpoint?
- Time zone of timestamps
- Currency of prices (assume ILS but confirm)

### Operational
- Webhook support for near-real-time updates? (huge if yes)
- Bulk export endpoint for backfill?
- Sandbox / test environment with non-production data
- Support contact for API issues

## What changes in our codebase

A short list:

1. **`backend/app/ingestion/comax_api_data_source.py`** — implement the 6 abstract methods.
2. **`backend/app/config.py`** — already has `COMAX_API_*` env vars (placeholder today, populated on Phase 2).
3. **`backend/app/ingestion/folder_watcher.py`** — extend to also handle a "pull from API on schedule" job. Same APScheduler.
4. **`.env`** — set `DATA_SOURCE=comax_api`.

Estimated effort once API docs and credentials are in hand: **3–5 days of engineering** for a clean implementation including tests, idempotency, and incremental sync.

## What does NOT change

- Database schema
- Analytics layer
- AI tools
- Dashboard UI
- Report generator
- Recommendation engine

That's the whole point of the abstraction.

## Migration day plan

1. Run the file-based system and the API-based system side-by-side for 7 days.
2. Compare totals: chain-wide net sales per day, inventory by store, item master row counts.
3. Investigate any deltas (usually time-zone or refund handling).
4. Cut over: `DATA_SOURCE=comax_api`, disable the folder watcher.
5. Keep `data/comax_reports/` as a manual fallback for when the API is down.

## Hybrid mode (optional)

If some data lives only in files and some only in the API (e.g. promotions are still managed in spreadsheets), a `CompositeDataSource(file=..., api=...)` lets each method route to the right source. Documented but not built until needed.
