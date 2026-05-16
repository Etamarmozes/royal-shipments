# Architecture

## Goal
A retail sales intelligence app whose only purpose is to help a CEO / commercial manager make a decision in under 10 seconds.

## Layered design

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend  (React + Vite + Tailwind, RTL Hebrew)            │
│  Dashboard · Imports · AI Chat · Reports · Admin            │
└──────────────────────────┬──────────────────────────────────┘
                           │ REST (JSON)
┌──────────────────────────▼──────────────────────────────────┐
│  API  (FastAPI)                                             │
│  /dashboard /imports /ai /reports /data /health             │
└──────────────────────────┬──────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┬──────────────┐
        ▼                  ▼                  ▼              ▼
   ┌─────────┐       ┌──────────┐      ┌────────────┐  ┌─────────┐
   │Services │       │Analytics │      │ AI tools   │  │ Reports │
   │         │       │  engine  │      │ (callable) │  │  gen.   │
   └────┬────┘       └────┬─────┘      └─────┬──────┘  └────┬────┘
        └────────────┬────┴──────────────────┘              │
                     ▼                                       │
                ┌─────────┐                                  │
                │ Repos   │                                  │
                └────┬────┘                                  │
                     ▼                                       ▼
                ┌─────────────────────────────────────────────┐
                │  SQLite (PostgreSQL-ready via SQLAlchemy)   │
                └─────────────────────────────────────────────┘
                     ▲
                     │ writes normalized rows
        ┌────────────┴────────────┐
        │  Ingestion              │
        │  ┌───────────────────┐  │
        │  │ DataSource (ABC)  │  │  Phase 2 swap point
        │  │ ├─ FileDataSource │  │  ◄─── Phase 1 (folder)
        │  │ └─ ComaxApiDS     │  │  ◄─── Phase 2 (API)
        │  └───────────────────┘  │
        │  Parser → Detector →    │
        │  Normalizer → Validator │
        └─────────────────────────┘
                     ▲
                     │ reads files
       data/comax_reports/  (you drop files here)
```

## Why this shape

- **Single ingestion entry point.** Whether a row comes from an Excel file today or the Comax API tomorrow, it flows through the same `DataSource` interface and lands in the same database tables. Nothing downstream cares where the data came from.
- **Analytics is pure functions over the DB.** The dashboard endpoints, the AI tools, and the report generator all call the same analytics layer. There is one source of truth for "top 10 items this week."
- **AI talks to tools, not to SQL.** The model can only call a fixed list of analysis functions (`get_top_items`, `compare_brands`, `detect_inventory_risks`, …). It cannot fabricate numbers or run arbitrary queries. Every answer is traceable.
- **Reports are a rendering of an analysis.** A JPG / PNG / PDF report is just an analytics result rendered as an image. Same numbers as the dashboard.

## Phase 1 vs Phase 2

| | Phase 1 (now) | Phase 2 (Comax API) |
|---|---|---|
| Source | `FileDataSource` (folder watch) | `ComaxApiDataSource` |
| Trigger | Manual run / scheduled scan | Scheduled API pull |
| Code change | None for downstream layers | Implement one class, swap a config flag |

## Module map (backend)

```
backend/app/
├── main.py              FastAPI app factory + lifespan
├── config.py            Pydantic settings, .env loader
├── database.py          SQLAlchemy engine + Session dependency
├── models/              ORM models (one file per aggregate)
├── schemas/             Pydantic response/request shapes
├── routers/             HTTP endpoints (thin)
├── services/            Orchestration (calls analytics + repos)
├── repositories/        DB query helpers
├── ingestion/
│   ├── data_source.py       abstract DataSource
│   ├── file_data_source.py  Phase 1 implementation
│   ├── comax_api_data_source.py  Phase 2 placeholder
│   ├── excel_parser.py      reads xlsx/xls/csv
│   ├── report_detector.py   identifies report type
│   ├── column_normalizer.py Hebrew↔English column mapping
│   └── folder_watcher.py    APScheduler job
├── analytics/
│   ├── sales_analyzer.py
│   ├── inventory_analyzer.py
│   └── recommendation_engine.py
├── ai/
│   ├── tools.py             function specs + implementations
│   └── agent.py             Anthropic SDK glue (tool use loop)
├── reports/
│   └── report_generator.py  HTML → JPG/PNG/PDF
└── utils/
    └── logging.py
```

## Frontend module map

```
frontend/src/
├── App.tsx              router + layout
├── main.tsx             entry
├── index.css            Tailwind + RTL
├── pages/
│   ├── Dashboard.tsx
│   ├── Imports.tsx
│   ├── AIChat.tsx
│   ├── Reports.tsx
│   └── Admin.tsx
├── components/
│   ├── Sidebar.tsx
│   ├── KpiCard.tsx
│   ├── AlertList.tsx
│   ├── TopList.tsx
│   └── DataFreshnessBadge.tsx
├── services/
│   └── api.ts           typed fetch wrappers
└── types/
    └── api.ts
```

## Non-goals (explicit)

- Not an ERP. Won't replace Comax.
- Not a generic BI tool. Every screen is opinionated about what matters.
- The AI doesn't run free-form SQL. Tool-use only.
- No multi-tenant SaaS in MVP. Single deployment per company.
