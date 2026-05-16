from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..ingestion import import_all_pending, import_file
from ..models import ImportLog

router = APIRouter(prefix="/imports", tags=["imports"])


@router.post("/run")
def run_import() -> dict:
    results = import_all_pending()
    return {"processed": len(results), "results": results}


@router.get("/logs")
def list_logs(limit: int = 50, db: Session = Depends(get_db)) -> list[dict]:
    rows = db.execute(
        select(ImportLog).order_by(desc(ImportLog.imported_at)).limit(limit)
    ).scalars().all()
    return [
        {
            "id": r.id,
            "file_name": r.file_name,
            "report_type": r.report_type,
            "status": r.status,
            "imported_at": r.imported_at.isoformat() if r.imported_at else None,
            "rows_detected": r.rows_detected,
            "rows_imported": r.rows_imported,
            "rows_failed": r.rows_failed,
            "data_date_min": r.data_date_min.isoformat() if r.data_date_min else None,
            "data_date_max": r.data_date_max.isoformat() if r.data_date_max else None,
            "warnings": r.warnings,
            "errors": r.errors,
        }
        for r in rows
    ]


@router.get("/status")
def status(db: Session = Depends(get_db)) -> dict:
    last_success = db.scalar(
        select(func.max(ImportLog.imported_at)).where(ImportLog.status.in_(["success", "partial"]))
    )
    by_type = db.execute(
        select(ImportLog.report_type, func.max(ImportLog.imported_at)).group_by(ImportLog.report_type)
    ).all()
    pending = sum(
        1 for p in settings.COMAX_REPORTS_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in {".xlsx", ".xls", ".xlsm", ".csv", ".tsv"}
    ) if settings.COMAX_REPORTS_DIR.exists() else 0
    return {
        "comax_reports_dir": str(settings.COMAX_REPORTS_DIR),
        "pending_files": pending,
        "last_successful_import": last_success.isoformat() if last_success else None,
        "by_report_type": {
            rt: ts.isoformat() if ts else None for rt, ts in by_type
        },
    }


@router.post("/upload")
def upload(file: UploadFile = File(...)) -> dict:
    suffix = Path(file.filename).suffix.lower()
    if suffix not in {".xlsx", ".xls", ".xlsm", ".csv", ".tsv"}:
        raise HTTPException(400, f"Unsupported file type: {suffix}")
    settings.COMAX_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    target = settings.COMAX_REPORTS_DIR / file.filename
    with target.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    result = import_file(target)
    return result
