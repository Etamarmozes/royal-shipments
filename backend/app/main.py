import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler

from .config import ALLOWED_ORIGINS, EMAIL_SYNC_INTERVAL_MINUTES
from .database import Base, engine, SessionLocal
from .routers import (
    shipments, containers, extra_work, email_router, pending_shipments,
    dashboard, alerts, events, export, gmail, pending, documents, receiving, ai,
    auth as auth_router, users as users_router,
    data_review as data_review_router, imports as imports_router,
    document_qc as document_qc_router,
)
from .services import alert_service, email_sync_service, auth_service, document_qc_service
from .services.auth_service import get_current_user
from fastapi import Depends
from .utils.migrations import add_missing_columns

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


def init_db():
    Base.metadata.create_all(bind=engine)
    # Add columns that exist on models but not yet in the DB (lightweight schema migration)
    add_missing_columns(engine)
    # Bootstrap an admin user if no users exist + seed QC supplier rules
    db = SessionLocal()
    try:
        auth_service.bootstrap_admin(db)
        document_qc_service.seed_builtin_rules(db)
    finally:
        db.close()


def background_jobs():
    """Hourly scans: alert engine + email-sync stub + Document Assignment QC.
    QC produces alerts only — never auto-reassigns."""
    db = SessionLocal()
    try:
        alert_service.scan_alerts(db)
        # In MVP we just touch last_sync; real Gmail integration plugs in here
        email_sync_service.sync_now(db)
        # Suspicious document assignments → QC results, never mutates links
        try:
            document_qc_service.run_scan(db)
        except Exception as e:
            logging.getLogger("scheduler").exception("QC scan failed: %s", e)
    finally:
        db.close()


scheduler = BackgroundScheduler(timezone="Asia/Jerusalem")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    if not scheduler.running:
        scheduler.add_job(
            background_jobs, "interval",
            minutes=EMAIL_SYNC_INTERVAL_MINUTES,
            next_run_time=None,
            id="hourly_scan",
        )
        scheduler.start()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(
    title="Royal Linen Shipments API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth router — public (login + me)
app.include_router(auth_router.router)

# All other routers require authentication. The dependency loads the user
# from JWT and 401s if missing/invalid. Per-route role checks live inside
# the routers themselves where needed.
auth_dep = [Depends(get_current_user)]
app.include_router(shipments.router, dependencies=auth_dep)
app.include_router(containers.router, dependencies=auth_dep)
app.include_router(extra_work.router, dependencies=auth_dep)
app.include_router(email_router.router, dependencies=auth_dep)
app.include_router(pending_shipments.router, dependencies=auth_dep)
app.include_router(dashboard.router, dependencies=auth_dep)
app.include_router(alerts.router, dependencies=auth_dep)
app.include_router(events.router, dependencies=auth_dep)
app.include_router(export.router, dependencies=auth_dep)
# Gmail OAuth callback uses redirect, can't carry Bearer token — leave open
# (still safe: Google's PKCE protects the auth code exchange)
app.include_router(gmail.router)
app.include_router(pending.router, dependencies=auth_dep)
app.include_router(documents.router, dependencies=auth_dep)
app.include_router(receiving.router, dependencies=auth_dep)
app.include_router(ai.router, dependencies=auth_dep)
# Users router has its own admin-only dependency
app.include_router(users_router.router)
# Data review + Excel import — own permission gates inside
app.include_router(data_review_router.router, dependencies=auth_dep)
app.include_router(imports_router.router, dependencies=auth_dep)
app.include_router(document_qc_router.router, dependencies=auth_dep)


@app.get("/")
def root():
    return {
        "app": "Royal Linen Shipments API",
        "version": "0.1.0",
        "docs": "/docs",
    }


@app.get("/health")
def health():
    return {"status": "ok"}
