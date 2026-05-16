"""Lightweight schema migrations — runs at startup.

For an MVP this is a smaller alternative to full Alembic.  It inspects
each table at startup and adds any column that exists on the SQLAlchemy
model but not yet in the database.  Drops are NOT supported (intentional
— losing data silently is worse than a slightly-stale schema).

Supports both SQLite (dev) and PostgreSQL (prod).  Dialect detected from
the engine at runtime.  For destructive / non-additive schema changes,
use Alembic — this runner only handles `ALTER TABLE ADD COLUMN`.
"""
from __future__ import annotations

import logging
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from ..database import Base

log = logging.getLogger("migrations")


# ----- type maps per dialect -----
# SQLite is loosely typed — most things go to TEXT/INTEGER.
_SQLITE_TYPE_MAP = {
    "INTEGER": "INTEGER",
    "VARCHAR": "TEXT",
    "TEXT":    "TEXT",
    "FLOAT":   "REAL",
    "BOOLEAN": "INTEGER",
    "DATETIME": "TEXT",
    "DATE":    "TEXT",
    "JSON":    "TEXT",
}

# PostgreSQL has proper types.  We map SQLAlchemy column-type class names
# directly to the native Postgres types.
_PG_TYPE_MAP = {
    "INTEGER":  "INTEGER",
    "VARCHAR":  "VARCHAR",
    "TEXT":     "TEXT",
    "FLOAT":    "DOUBLE PRECISION",
    "BOOLEAN":  "BOOLEAN",
    "DATETIME": "TIMESTAMP",
    "DATE":     "DATE",
    "JSON":     "JSONB",
}


def _column_type_sql(col_type, dialect_name: str) -> str:
    name = type(col_type).__name__.upper()
    if dialect_name == "postgresql":
        return _PG_TYPE_MAP.get(name, "TEXT")
    return _SQLITE_TYPE_MAP.get(name, "TEXT")


def _column_default_sql(col, dialect_name: str) -> str:
    """Render the Python-side default as a SQL DEFAULT clause (best-effort).
    Without this, ALTER TABLE ADD COLUMN leaves all existing rows NULL —
    which silently breaks `WHERE col == False` filters in SQLAlchemy.
    """
    d = col.default
    if d is None:
        return ""
    if d.is_scalar:
        v = d.arg
        if isinstance(v, bool):
            if dialect_name == "postgresql":
                return f" DEFAULT {'TRUE' if v else 'FALSE'}"
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
    dialect_name = engine.dialect.name   # "sqlite" / "postgresql" / …
    if dialect_name not in ("sqlite", "postgresql"):
        log.warning(
            "add_missing_columns: dialect=%s not supported, skipping. "
            "Use Alembic for managed migrations.",
            dialect_name,
        )
        return

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
            col_type = _column_type_sql(col.type, dialect_name)
            default_sql = _column_default_sql(col, dialect_name)
            # Both SQLite and Postgres accept double-quoted identifiers.
            ddl = f'ALTER TABLE "{table_name}" ADD COLUMN "{col.name}" {col_type}{default_sql}'
            log.info("MIGRATE: %s", ddl)
            try:
                with engine.begin() as conn:
                    conn.execute(text(ddl))
                    # Backfill existing rows so the column never reads NULL
                    # against a Python default of False / 0 / "" .  Postgres
                    # already does this for ADD COLUMN ... DEFAULT, but SQLite
                    # only does it on 3.35+ — do it explicitly to be safe.
                    if default_sql:
                        default_literal = default_sql.replace(" DEFAULT ", "")
                        conn.execute(text(
                            f'UPDATE "{table_name}" SET "{col.name}" = '
                            + default_literal
                            + f' WHERE "{col.name}" IS NULL'
                        ))
            except Exception as e:
                log.warning("MIGRATE failed for %s.%s: %s", table_name, col.name, e)
