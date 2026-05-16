from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import ImportLog, InventorySnapshot, Sale

router = APIRouter(tags=["health"])


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    last_import = db.scalar(select(func.max(ImportLog.imported_at)))
    last_sales = db.scalar(select(func.max(Sale.date)))
    last_inv = db.scalar(select(func.max(InventorySnapshot.snapshot_date)))
    return {
        "status": "ok",
        "now": datetime.now(timezone.utc).isoformat(),
        "data_source": settings.DATA_SOURCE,
        "last_import_at": last_import.isoformat() if last_import else None,
        "last_sales_date": last_sales.isoformat() if last_sales else None,
        "last_inventory_date": last_inv.isoformat() if last_inv else None,
        "watcher_enabled": settings.WATCHER_ENABLED,
        "ai_configured": bool(settings.ANTHROPIC_API_KEY),
    }
