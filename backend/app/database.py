"""SQLAlchemy engine + session factory.

Works against either SQLite (local dev) or PostgreSQL (production).
The DATABASE_URL env var drives the dialect:

  sqlite:///./data/royal_linen.db           ← local dev (default)
  postgresql+psycopg2://user:pass@host/db   ← production
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session

from .config import DATABASE_URL

# `check_same_thread=False` is a SQLite-only argument.  On Postgres it
# causes a TypeError, so we only pass it when the URL is SQLite.
_engine_kwargs: dict = {}
if DATABASE_URL.startswith("sqlite"):
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    # Production: tune the connection pool.  These numbers are conservative
    # — bump pool_size for higher concurrency once we know real load.
    _engine_kwargs.update(
        pool_pre_ping=True,   # drop dead connections (Hetzner / NAT timeouts)
        pool_size=10,
        max_overflow=20,
        pool_recycle=1800,    # 30 min — well under typical idle-close windows
    )

engine = create_engine(DATABASE_URL, **_engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
