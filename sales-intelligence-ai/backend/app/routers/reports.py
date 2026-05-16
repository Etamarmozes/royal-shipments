from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import GeneratedReport
from ..reports import generate_report
from ..schemas.common import ReportRequest

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("/generate")
def generate(req: ReportRequest, db: Session = Depends(get_db)) -> dict:
    return generate_report(
        db,
        topic=req.topic,
        date_range=req.date_range,
        fmt=req.format,
        layout=req.layout,
        params=req.params,
    )


@router.get("")
def list_reports(limit: int = 50, db: Session = Depends(get_db)) -> list[dict]:
    rows = db.execute(
        select(GeneratedReport).order_by(desc(GeneratedReport.generated_at)).limit(limit)
    ).scalars().all()
    return [
        {
            "id": r.id,
            "title": r.title,
            "report_type": r.report_type,
            "format": r.format,
            "generated_at": r.generated_at.isoformat() if r.generated_at else None,
            "file_path": r.file_path,
        }
        for r in rows
    ]


@router.get("/{report_id}/download")
def download(report_id: int, db: Session = Depends(get_db)) -> FileResponse:
    row = db.get(GeneratedReport, report_id)
    if row is None:
        raise HTTPException(404, "Report not found")
    p = Path(row.file_path)
    if not p.exists():
        raise HTTPException(410, "File no longer exists on disk")
    return FileResponse(p, filename=p.name)
