# Sales Intelligence AI

A commercial intelligence command center for retail sales management.
Not a dashboard. Not an Excel reader. Not a chat. A decision engine.

It answers, in 10 seconds:

1. What happened?
2. Is it good or bad — compared to what?
3. Where is the problem?
4. Where is the opportunity?
5. What should we do now?

---

## What this app does

- Reads daily sales / inventory / item reports you drop into a folder (Comax Excel/CSV exports)
- Detects the report type automatically, normalizes Hebrew + English columns, validates data
- Stores everything in a structured SQLite database (PostgreSQL-ready)
- Shows an executive dashboard: KPIs, top/bottom performers, store ranking, brand comparison, inventory alerts
- Lets you ask questions in Hebrew or English (AI chat with traceable, real-data answers)
- Generates JPG / PNG / PDF executive reports for WhatsApp, email, or CEO updates
- Recommends concrete actions: reorder, transfer between stores, stop buying, run a promo, fix a weak store

When Comax API access is available later, only the data source layer changes — dashboards, AI, and reports keep working.

---

## Setup — for non-developers

You need two things installed once:

1. **Python 3.11 or newer** — https://www.python.org/downloads/ (during install, tick "Add Python to PATH")
2. **Node.js 20 or newer** — https://nodejs.org/

That's it. Now run these commands in order from this folder (`sales-intelligence-ai`).

### Step 1 — bootstrap the project

```
python setup_project.py
```

This verifies the folder tree, creates anything missing, copies sample demo data, and prints what to do next.

### Step 2 — install backend dependencies and seed demo data

```
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m app.seed_demo_data
```

(On Mac/Linux replace `.venv\Scripts\activate` with `source .venv/bin/activate`.)

### Step 3 — start the backend

```
uvicorn app.main:app --reload --port 8000
```

Leave this terminal running. The API is now at http://localhost:8000 and docs at http://localhost:8000/docs.

### Step 4 — install frontend and start it (new terminal)

```
cd sales-intelligence-ai\frontend
npm install
npm run dev
```

Open http://localhost:5173 in your browser.

### Step 5 — drop a real Comax report

Put any Excel or CSV export from Comax into:

```
sales-intelligence-ai\data\comax_reports\
```

Then in the app, go to **Imports** → **Run import**. The system will detect the report type, import the data, and update the dashboard.

---

## Folder map

| Folder | Purpose |
|---|---|
| `data/comax_reports/` | **Drop new daily reports here** |
| `data/imported/` | Successfully imported files (auto-moved here) |
| `data/failed/` | Files that failed import + error log |
| `data/archive/` | Older imported reports |
| `data/sample/` | Demo data shipped with the app |
| `reports/jpg/` `png/` `pdf/` | Generated executive reports |
| `exports/` | Excel exports |
| `logs/` | System and import logs |
| `docs/` | Architecture, schema, AI tools, deployment |
| `backend/` | FastAPI Python backend |
| `frontend/` | React + Vite + Tailwind frontend |

---

## Where to read more

- `docs/architecture.md` — how the pieces fit together
- `docs/database_schema.md` — every table and column
- `docs/import_flow.md` — how a file becomes data
- `docs/ai_tools.md` — what the AI can actually do
- `docs/dashboard_design.md` — the executive screens
- `docs/report_generator.md` — JPG / PNG / PDF layouts
- `docs/deployment.md` — running it for real
- `docs/comax_api_future_integration.md` — Phase 2 plan

---

## Important

This project lives entirely inside `sales-intelligence-ai/` and does **not** touch the existing royal-linen-shipments-app code, database, or config.
