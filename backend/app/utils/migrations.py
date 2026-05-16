"""Lightweight schema migrations for SQLite — runs at startup.

For an MVP using SQLite, full Alembic is overkill. Instead, we inspect
each table at startup and add any columns that exist on the SQLAlchemy
model but not yet in the database. Drops are NOT supported (intentional —
losing data silently is worse than a slightly-stale schema).
"""
from __future__ import annotations

import logging
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from ..database import Base

log = logging.getLogger("migrations")


# Map SQLAlchemy column types → SQLite column type literal
_TYPE_MAP = {
    "INTEGER": "INTEGER",
    "VARCHAR": "TEXT",
    "TEXT": "TEXT",
    "FLOAT": "REAL",
    "BOOLEAN": "INTEGER",
    "DATETIME": "TEXT",
    "DATE": "TEXT",
    "JSON": "TEXT",
}


def _sqlite_type(col_type) -> str:
    name = type(col_type).__name__.upper()
    return _TYPE_MAP.get(name, "TEXT")


def _column_default_sql(col) -> str:
    """Render the Python-side default as a SQL DEFAULT clause (best-effort).
    Without this, ALTER TABLE ADD COLUMN leaves all existing rows NULL —
    which silently breaks `WHERE col == False` filters in SQLAlchemy."""
    d = col.default
    if d is None:
        return ""
    if d.is_scalar:
        v = d.arg
        if isinstance(v, bool):
            return f" DEFAULT {1 if v else 0}"
        if isinstance(v, int):
            return f" DEFAULT {int(v)}"
        if isinstance(v, float):
            return f" DEFAULT {float(v)}"
        if isinstance(v, str):
            esc = v.replace("'", "''")
            return f" DEFAULT '{esc}'"
    return ""


def add_missing_columns(engine: Engine) -> None:
    insp = inspect(engine)
    existing_tables = set(insp.get_table_names())
    for table_name, table in Base.metadata.tables.items():
        if table_name not in existing_tables:
            # create_all() handles new tables — nothing to migrate.
            continue

        existing_cols = {c["name"] for c in insp.get_columns(table_name)}
        for col in table.columns:
            if col.name in existing_cols:
                continue
            sqlite_type = _sqlite_type(col.type)
            default_sql = _column_default_sql(col)
            ddl = f'ALTER TABLE "{table_name}" ADD COLUMN "{col.name}" {sqlite_type}{default_sql}'
            log.info("MIGRATE: %s", ddl)
            try:
                with engine.begin() as conn:
                    conn.execute(text(ddl))
                    # Backfill: ALTER ADD COLUMN with DEFAULT only sets new
                    # rows; for SQLite ≥3.35 it backfills existing too, but
                    # for older versions and to be safe, do it explicitly.
                    if default_sql:
                        backfill = f'UPDATE "{table_name}" SET "{col.name}" = (SELECT "{col.name}" FROM "{table_name}" WHERE "{col.name}" IS NOT NULL LIMIT 1) WHERE "{col.name}" IS NULL'
                        # Simpler: re-run with literal default
                        conn.execute(text(
                            f'UPDATE "{table_name}" SET "{col.name}" = '
                            + default_sql.replace(" DEFAULT ", "")
                            + f' WHERE "{col.name}" IS NULL'
                        ))
            except Exception as e:
                log.warning("MIGRATE failed for %s.%s: %s", table_name, col.name, e)
