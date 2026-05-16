# Report generator

Turns an analysis result into a shareable artifact: JPG / PNG / PDF / XLSX.

## How it works

```
request                 analysis layer            renderer              output
───────────             ───────────────           ────────              ──────
{topic, date,    →     run the matching     →   Jinja2 HTML      →   imgkit/wkhtmltoimage
 layout, fmt}          tool(s) → JSON           template +            → JPG/PNG
                       payload                  Tailwind          →   weasyprint
                                                                      → PDF
                                                                  →   openpyxl
                                                                      → XLSX
```

The renderer is intentionally HTML-based: design changes are CSS, not Python.

## Layouts

| layout key | size | use case |
|---|---|---|
| `whatsapp` | 1080 × 1920 (vertical) | quick share to a WhatsApp group |
| `desktop` | 1600 × 900 | email / Slack / pinned in dashboards |
| `ceo_one_pager` | 2480 × 3508 (A4) | weekly executive update |
| `analyst_detail` | A4 multi-page | deep dive |
| `store_ranking` | 1600 × 1200 | one bar chart, one table |
| `brand_comparison` | 1600 × 1200 | head-to-head |
| `item_performance` | 1080 × 1080 (square) | single SKU brief |
| `inventory_risk` | 1600 × 1200 | reorder + transfer + stop-buy lists |

Every layout includes:

- Title + subtitle (period, scope)
- Data freshness chip (`Sales updated 2h ago`)
- 3–5 KPI cards
- One chart **or** one table (not both, except `analyst_detail`)
- One paragraph **insight**
- One paragraph **recommended action**
- Footer: generation timestamp, data source list

## Anti-patterns the templates enforce

- No naked numbers without a comparison.
- No more than 7 lines of text on a `whatsapp` layout.
- No raw item codes in the title (use brand + item name).
- Action paragraph must start with an imperative verb (Reorder, Transfer, Stop, Promote, Investigate).

## Brand comparison example

Request: `"תוציא לי דוח JPG של קדס מול אדידס החודש לפי סניפים עם מסקנה והמלצה"`

Pipeline:
1. `compare_brands(brand_a="Keds", brand_b="Adidas", date_range="this_month", group_by="store")`
2. `generate_visual_report(topic="brand_comparison", layout="whatsapp", format="jpg", payload=...)`

Renders to `reports/jpg/brand_comparison_keds_vs_adidas_2026-05.jpg` and is saved to `generated_reports`.

Template fields:

```
{{ title }}                    ← "Keds vs Adidas — מאי 2026"
{{ freshness_chip }}
{{ kpi.totals_a }}             ← gross sales / units / AOV
{{ kpi.totals_b }}
{{ table.store_rows }}         ← store, A_sales, B_sales, winner, gap%
{{ insight_paragraph }}        ← analyst layer fills this
{{ action_paragraph }}         ← recommendation engine fills this
{{ generated_at }}
{{ data_sources }}
```

## CEO summary

`generate_ceo_summary(date_range)` returns a payload with:

- 3 wins (with numbers)
- 3 problems (with numbers)
- 3 recommended actions
- 1 line "what to watch this week"

The `ceo_one_pager` layout renders it as A4. Default font: Heebo (Hebrew + Latin), so the same template renders Hebrew and English without layout shift.

## File naming

```
reports/<format>/<report_type>_<scope>_<period>_<YYYY-MM-DD-HHMMSS>.<ext>
```

Examples:

```
reports/jpg/brand_comparison_keds_vs_adidas_2026-05_2026-05-03-101422.jpg
reports/pdf/ceo_one_pager_chain_2026-05_2026-05-03-101422.pdf
reports/png/store_ranking_chain_last7d_2026-05-03-101422.png
```

## Performance

- Image rendering target: under 2 seconds for `whatsapp` and `desktop` layouts.
- PDF target: under 5 seconds for `ceo_one_pager`.
- Chart rendering: pre-computed SVG (matplotlib or vega-lite via altair) embedded in the HTML — no headless chart JS needed.

## Dependencies (Python)

- `jinja2` — templating
- `imgkit` (calls `wkhtmltoimage`) **or** `playwright` headless screenshot — JPG/PNG
- `weasyprint` — PDF
- `openpyxl` — XLSX
- `matplotlib` or `altair` — charts to SVG/PNG embedded in HTML

`wkhtmltoimage` requires a system install. Alternatively the MVP can use `playwright` (`pip install playwright && playwright install chromium`), which is heavier but pure Python to operate. The default `report_generator.py` checks which is available and uses it.

## Where they go

All generated files land under `reports/<format>/` and a row is inserted into `generated_reports`. The frontend's "Generated reports" page lists them with download links.
