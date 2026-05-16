# AI tools

The AI is not allowed to write SQL. It can only call a fixed list of analysis functions. Every answer is therefore traceable to a real DB query.

## Conversation loop

```
user question
   │
   ▼
Anthropic Claude (Sonnet 4.6) with tool definitions
   │
   ├── tool_use: get_sales_summary({date_range:"this_month"})
   │       │
   │       ▼  Python executes the function against SQLite
   │       └─► result = {gross_sales: 1_240_000, ...}
   │
   ├── tool_use: compare_brands({brand_a:"Keds", brand_b:"Adidas", date_range:"this_month"})
   │       │
   │       ▼
   │       └─► result = {...}
   │
   ▼
Final answer (structured: bottom line · numbers · meaning · action · confidence)
```

If `ANTHROPIC_API_KEY` is not set, the system falls back to a deterministic rule-based responder that maps Hebrew/English keywords to the same tools and returns a templated answer. It is less natural but uses the same numbers.

## Tool catalog

Each tool has a JSON Schema (Anthropic-compatible) and a Python implementation. All return JSON-serializable dicts.

### `get_sales_summary`
> Headline numbers for any period.

Input: `{ date_range: str | {from, to}, store_ids?: int[], brand_ids?: int[], category_ids?: int[] }`
Output: `{ gross_sales, net_sales, units, transactions, avg_selling_price, gross_margin?, vs_previous_period: {pct, abs}, period_label }`

### `get_top_items` / `get_bottom_items`
Input: `{ date_range, limit=10, by="net_sales"|"units"|"margin", filters? }`
Output: `[{ item_id, item_name, brand, category, value, share_pct, vs_prev_pct }, ...]`

### `compare_brands`
Input: `{ brand_a, brand_b, date_range, group_by="store"|"category"|"none" }`
Output: `{ a: {totals, top_stores, weak_stores}, b: {totals, top_stores, weak_stores}, head_to_head: [...], insight: str }`

### `analyze_store_performance`
Input: `{ date_range, store_id? }`
Output: `{ ranking: [...], peers_comparison: [...], anomalies: [...] }`

### `detect_inventory_risks`
Input: `{ days_lookback=30 }`
Output:
```json
{
  "fast_moving_low_stock": [...],
  "slow_moving_high_stock": [...],
  "stuck_items":            [...],
  "stockout_in_strong_stores": [...]
}
```

### `detect_slow_moving_items`
Threshold: ≥ N days inventory cover, < M units sold/week. Tunable via params.

### `detect_fast_moving_low_stock_items`
Threshold: < K days inventory cover at current sales velocity.

### `compare_periods`
Input: `{ current_period, previous_period, filters? }`
Output: `{ deltas_by_brand, deltas_by_category, deltas_by_store, biggest_movers }`

### `generate_ceo_summary`
Input: `{ date_range }`
Output: a structured payload — bullet points, top 3 wins, top 3 problems, top 3 actions. Used by the report generator and the chat.

### `generate_action_plan`
Input: `{ date_range, max_actions=10 }`
Output: list of `{ action, target (item/store/brand), priority, why, expected_impact, confidence }`.

### `generate_visual_report`
Input: `{ topic, date_range, format="jpg"|"png"|"pdf", layout="whatsapp"|"desktop"|"ceo_one_pager" }`
Output: `{ file_path, file_url, title, summary }`. Calls the report generator under the hood.

### `get_store_ranking`
Input: `{ date_range, by="net_sales"|"units"|"yoy_growth", filters? }`
Output: `[{ rank, store, value, vs_prev_pct, flags: [...] }]`

### `get_item_performance`
Input: `{ item_or_barcode, date_range }`
Output: per-store breakdown + trend.

### `get_brand_performance` / `get_category_performance`
Same shape, different dimension.

## Answer contract

Every AI response (chat or report) follows this structure:

1. **Bottom line** — one sentence, decision-grade.
2. **Key numbers** — the 3–5 figures that matter, with units and period.
3. **What it means** — interpretation, not just restatement.
4. **Problem / opportunity** — explicit.
5. **Recommended action** — concrete, with priority.
6. **Data limitations** — "inventory data missing for 3 stores", "based on sales only", etc.

The AI is instructed to refuse to invent numbers. If a tool returns empty, the answer states that no data was found for the requested filter.

## Hebrew + English

Tools accept Hebrew brand / category / store names and resolve them via fuzzy match against the dimension tables (case- and niqqud-insensitive). The model is prompted in both languages and answers in the language of the question.

## Logging

Every chat exchange writes to `ai_analysis_logs` with: question, final answer, list of tool calls + arguments + result hashes, and the data freshness snapshot at the time of the answer.
