# Dashboard design

## Principle

The dashboard is **not a screen of charts**. It is a triage panel.
Within 10 seconds the user must be able to answer: *what needs my attention right now?*

Information hierarchy, top to bottom:

1. **Status** (KPIs + freshness)
2. **Alerts** (problems sorted by priority)
3. **Opportunities** (concrete recommendations)
4. **Performance** (top / bottom lists)
5. **Drill-downs** (store / brand / category / item)

The first viewport contains 1–3. Everything else lives below the fold or behind a tab.

## Layout (desktop, RTL)

```
┌──────────────────────────────────────────────────────────────────────┐
│ Sidebar  │  Header: company · period selector · data freshness chip │
│  · Dash  │                                                          │
│  · Imp.  │  ┌───── KPI ROW ─────────────────────────────────────┐   │
│  · AI    │  │ Sales today │ Sales MTD │ vs last │ Units │ AOV │   │
│  · Rep.  │  └───────────────────────────────────────────────────┘   │
│  · Adm.  │                                                          │
│          │  ┌──── ALERTS (red/yellow) ──────────────────────┐      │
│          │  │ • Adidas X stockout in flagship stores       │      │
│          │  │ • Keds 39 dropped 31% WoW in 4 outlets        │      │
│          │  │ • Item 8810 has 90 days inventory cover      │      │
│          │  └────────────────────────────────────────────────┘      │
│          │                                                          │
│          │  ┌──── ACTIONS RECOMMENDED ───────────────────────┐     │
│          │  │ ▶ Reorder 3 SKUs (high priority)              │     │
│          │  │ ▶ Transfer 24 units Bnei Brak → Kiryat Ono   │     │
│          │  │ ▶ Review price on slow-moving 12 items        │     │
│          │  └────────────────────────────────────────────────┘     │
│          │                                                          │
│          │  ┌── Top items ──┐  ┌── Bottom items ──┐                │
│          │  │ ...            │  │ ...               │                │
│          │  └────────────────┘  └───────────────────┘                │
│          │                                                          │
│          │  ┌── Store ranking ─────────────────────┐                │
│          │  │ bar chart + flags                    │                │
│          │  └──────────────────────────────────────┘                │
└──────────────────────────────────────────────────────────────────────┘
```

## Mobile

Single column, same order. KPI row becomes a horizontal scroll of cards. Charts collapse to summary stats with "view chart" expand.

## Visual language

- **Status colors**: `green` = ahead of comparison, `amber` = within ±5%, `red` = behind by >5%, `gray` = no comparison data.
- **One number per card**, with a subtitle for context (`vs. last period`, `% of total`, `target gap`).
- **Charts** prefer bar over line for ranking, line for trend, never pie.
- **No raw IDs** in user-facing labels. Items show as `Brand · Item name · Code` with code subdued.
- **Empty states are not blank.** When data is missing the card explains *why* (`No inventory report imported in 3 days — drop a file in data/comax_reports/`).

## Period selector

`Today | Yesterday | This week | Last 7 days | This month | Last 30 days | Last 90 days | Custom`.
Default = `This month`. The choice persists per user (localStorage in MVP).

## Data freshness chip

Always visible in the header.

```
[ ✓ Sales 2h ago · Inventory 9h ago ]      ← green
[ ⚠ Sales 26h ago · Inventory 3d ago ]     ← amber
[ ✗ No sales import in 5 days ]            ← red, click → /imports
```

## KPI row — what's shown

| KPI | Definition | Compare to |
|---|---|---|
| Sales today | Sum `net_sales` where date = today | Same weekday last week |
| Sales MTD | Sum `net_sales` MTD | Same MTD last month |
| Units | Sum `quantity` for selected period | Previous period |
| AOV | `net_sales / transaction_count` | Previous period |
| Active SKUs | Distinct items with sales > 0 | — |
| Weak stores | Count stores with sales < 70% of peer median | — |
| Stock-risk items | Count items with cover < 7 days | — |
| Stuck items | Count items with cover > 90 days, sales < 1 unit/week | — |

## Alerts ranking

Each alert has a **priority score** = `severity × business_value × actionability`.

- **severity** = how far from peer/historical baseline (z-score)
- **business_value** = item / store revenue weight
- **actionability** = does the system have a concrete recommendation? (binary 0/1)

Top 5 surface on the dashboard; the rest live on the dedicated alerts page.

## Drill paths

- KPI card click → period-locked breakdown by store / brand / category
- Alert click → item or store detail page with the underlying numbers and the recommended action pre-filled
- Top/Bottom row click → item performance page (per-store breakdown, 30-day trend, inventory state)
