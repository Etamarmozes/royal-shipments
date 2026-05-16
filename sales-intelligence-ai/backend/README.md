# Backend — Sales Intelligence AI

FastAPI + SQLAlchemy + SQLite. PostgreSQL-ready.

## Run

```
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # Mac/Linux
pip install -r requirements.txt
python -m app.seed_demo_data    # creates DB + loads demo data
uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

## Layout

```
app/
├── main.py             FastAPI factory
├── config.py           Settings from .env
├── database.py         SQLAlchemy engine
├── models/             ORM models
├── schemas/            Pydantic shapes
├── routers/            HTTP endpoints
├── services/           Orchestration
├── repositories/       DB queries
├── ingestion/          File → DB pipeline + DataSource abstraction
├── analytics/          Sales / inventory / recommendations
├── ai/                 Tool definitions + Claude agent
├── reports/            JPG / PNG / PDF generation
├── utils/              Logging
└── seed_demo_data.py   One-shot demo loader
```

## Tests

```
pytest
```
