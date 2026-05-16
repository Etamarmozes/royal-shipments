# Sample demo data

These files demonstrate the report formats the system understands.

| File | Format demonstrated |
|---|---|
| `sample_stores.csv` | Stores master (English headers) |
| `sample_items.csv` | Items master (English headers) — Keds, Adidas, Nautica, Lifetime |
| `sample_sales_hebrew.csv` | Daily sales with Hebrew headers (תאריך, סניף, כמות, מכר ברוטו…) |
| `sample_inventory.csv` | Inventory snapshot per store/item |

**These are demo files. The seed script (`backend/python -m app.seed_demo_data`) loads a much larger synthetic dataset that demonstrates real business patterns:**

- Keds outperforms Adidas in price-sensitive stores (Beit Shemesh, Ashdod, Kiryat Yam)
- Adidas dominates flagship/general stores (Kiryat Ono, Bnei Brak, Netanya)
- Some Adidas SKUs are nearly out of stock in flagship stores (`fast_moving_low_stock` alerts)
- Some Nautica / Lifetime SKUs are stuck (`slow_moving_high_stock` alerts)

After seeding, the dashboard, AI chat, and report generator have realistic numbers to work with.

To test the import flow with these CSVs, copy any of them into `data/comax_reports/` and trigger an import from the UI or `POST /imports/run`.
