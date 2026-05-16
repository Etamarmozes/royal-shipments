"""Excel shipment import endpoints — template / preview / apply.

Multi-format preview supports:
  - royal_linen_template (our own format — full preview + apply path)
  - icl                  (preview-only for now — apply path deferred)
  - eli_line             (preview-only for now — apply path deferred)

The /preview endpoint dispatches automatically by format detection.
The /apply endpoint ONLY accepts the royal_linen_template format —
external formats require explicit user approval before any DB write
and a separate apply path that we'll add once the user reviews the
preview.
"""
import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User, Shipment, Container, ImportBatch
from ..services import excel_import_service, external_import_service
from ..services.excel_format_detector import detect_format
from ..services.external_excel_parsers import parse_icl, parse_eli_line
from ..services.external_dedup_service import (
    find_matches, default_action_for, UNSAFE_CREATE_LEVELS,
)
from ..services.auth_service import require_permission

router = APIRouter(prefix="/import", tags=["import"])
log = logging.getLogger("import")


@router.get("/excel/template")
def download_template(
    actor: User = Depends(require_permission("shipment.read")),
):
    """Download the Excel shipment import template (.xlsx)."""
    path = excel_import_service.write_template_to_disk()
    return FileResponse(
        str(path),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="shipment_import_template.xlsx",
    )


def _dedup_for_external_row(db: Session, row: Dict[str, Any]) -> Dict[str, Any]:
    """Score the row against every active shipment. Returns the rich
    similarity verdict + a back-compat `match` shape for older clients.

    NEVER writes. Read-only.
    """
    verdict = find_matches(db, row)

    # Back-compat: the existing UI checks `_match` for a yes/no
    # duplicate. We mirror it from the top-scoring possible match,
    # but only when the level is exact_duplicate (so older callers
    # don't auto-update on soft matches).
    legacy_match = None
    if verdict["match_level"] == "exact_duplicate" and verdict["matched_shipment_id"]:
        # Pick a friendly "matched_by" string from the top reason
        matched_by = "score"
        for r in verdict["match_reasons"]:
            if "shipment_reference" in r or "ICL file" in r or "JOB" in r:
                matched_by = "shipment_reference"; break
            if "BL" in r or "BOL" in r:
                matched_by = "bl_number"; break
            if "PO" in r:
                matched_by = "po_number"; break
            if "Invoice" in r:
                matched_by = "invoice_number"; break
        legacy_match = {
            "id": verdict["matched_shipment_id"],
            "shp_id": verdict["matched_shipment_reference"],
            "matched_by": matched_by,
        }

    return {
        "match": legacy_match,
        "match_level": verdict["match_level"],
        "match_score": verdict["match_score"],
        "match_reasons": verdict["match_reasons"],
        "matched_shipment_id": verdict["matched_shipment_id"],
        "matched_shipment_reference": verdict["matched_shipment_reference"],
        "matched_shipment_supplier": verdict["matched_shipment_supplier"],
        "possible_matches": verdict["possible_matches"],
    }


@router.post("/excel/preview")
async def preview_excel(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("shipment.create")),
):
    """Multi-format Excel preview. PREVIEW ONLY — never writes to DB.

    Detects format → dispatches:
      royal_linen_template → existing parser, apply-eligible
      icl                  → ICL parser, preview-only
      eli_line             → Eli Line parser, preview-only

    Response shape (all formats):
      {
        format: "icl" | "eli_line" | "royal_linen_template" | "unknown",
        format_info: { sheet_name, header_row, source_provider, notes },
        file_errors: [...],
        rows: [...],
        summary: { total_rows, create, update, skip, error, needs_review,
                   unique_suppliers, unique_containers },
        applyable: bool,   # false for ICL/Eli Line (apply path not yet built)
      }
    """
    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="קובץ ריק")

    fmt, info = detect_format(contents)
    fname = file.filename or "uploaded.xlsx"

    # Royal Linen template — existing path
    if fmt == "royal_linen_template":
        result = excel_import_service.preview(db, contents)
        return {
            "format": fmt,
            "format_info": info,
            **result,
            "applyable": True,
        }

    # ICL or Eli Line — preview AND now apply-eligible (with explicit user
    # confirmation in the apply endpoint).
    rows: List[Dict[str, Any]] = []
    if fmt == "icl":
        rows = parse_icl(
            contents,
            sheet_name=info.get("sheet_name"),
            header_row=info.get("header_row", 15),
            data_first_row=info.get("data_first_row", 16),
            source_file_name=fname,
        )
    elif fmt == "eli_line":
        rows = parse_eli_line(
            contents,
            sheet_name=info.get("sheet_name"),
            data_first_row=info.get("data_first_row", 3),
            source_file_name=fname,
        )
    else:
        return {
            "format": "unknown",
            "format_info": info,
            "file_errors": [
                "פורמט הקובץ לא זוהה. נתמכים: Royal Linen template / ICL / Eli Line."
            ],
            "rows": [],
            "summary": {},
            "applyable": False,
        }

    # Run dedup + similarity against the live shipments table — read-only
    counts = {"create": 0, "update": 0, "skip": 0, "error": 0,
              "needs_review": 0,
              "exact_duplicate": 0, "strong_match": 0, "soft_match": 0}
    suppliers, containers = set(), set()
    for r in rows:
        dup = _dedup_for_external_row(db, r)
        # Attach all dedup fields onto the row for the UI
        r["_match"] = dup["match"]
        r["match_level"] = dup["match_level"]
        r["match_score"] = dup["match_score"]
        r["match_reasons"] = dup["match_reasons"]
        r["matched_shipment_id"] = dup["matched_shipment_id"]
        r["matched_shipment_reference"] = dup["matched_shipment_reference"]
        r["matched_shipment_supplier"] = dup["matched_shipment_supplier"]
        r["possible_matches"] = dup["possible_matches"]

        if r.get("supplier_name"):
            suppliers.add(r["supplier_name"])
        if r.get("container_quantity"):
            containers.add(f"{r.get('shipment_reference')}/{r['container_quantity']}")

        # Smart default: review > exact > strong > soft > new
        needs_review = bool(r.get("needs_review"))
        r["_action_default"] = default_action_for(dup["match_level"], needs_review)

        # Counters
        if needs_review:
            counts["needs_review"] += 1
        if dup["match_level"] == "exact_duplicate":
            counts["exact_duplicate"] += 1
        elif dup["match_level"] == "strong_possible_match":
            counts["strong_match"] += 1
        elif dup["match_level"] == "soft_possible_match":
            counts["soft_match"] += 1
        if r["_action_default"] == "create":
            counts["create"] += 1
        elif r["_action_default"] == "update":
            counts["update"] += 1
        else:
            counts["skip"] += 1

    summary = {
        "total_rows": len(rows),
        **counts,
        "unique_suppliers": len(suppliers),
        "unique_containers": len(containers),
    }

    return {
        "format": fmt,
        "format_info": info,
        "file_errors": [],
        "rows": rows,
        "summary": summary,
        # ICL / Eli Line apply path is now wired. The UI must still:
        #   1. Let the user pick create/update/skip per row
        #   2. Default needs_review rows to "skip"
        #   3. Require typing "APPLY" to confirm
        #   4. NEVER auto-apply on upload
        "applyable": True,
    }


class ApplyRequest(BaseModel):
    rows: List[Dict[str, Any]]
    confirm: str  # must be "APPLY" — defends against accidental writes


@router.post("/excel/apply")
def apply_excel(
    payload: ApplyRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("shipment.create")),
):
    """Apply the user-approved rows. Each row needs `_action` ∈
    {create, update, skip}.

    SAFETY:
      - Requires `confirm: "APPLY"` (the UI must collect this from the
        user — typing "APPLY" into a confirm field).
      - Dispatches by `source_provider` on each row:
          ICL / Eli Line → external_import_service (with import_batch
                          tracking + rollback support)
          else (Royal Linen Template / unset) → excel_import_service
    """
    if payload.confirm != "APPLY":
        raise HTTPException(
            status_code=400,
            detail="פעולה זו דורשת אישור: שלח 'confirm': 'APPLY'",
        )
    if not payload.rows:
        raise HTTPException(status_code=400, detail="אין שורות לייבוא")

    actor_name = actor.full_name or actor.username

    # Group rows by source_provider — each batch comes from one file
    providers = {r.get("source_provider") for r in payload.rows}
    external = providers - {None, "", "Royal Linen Template"}
    is_external = bool(external)

    if is_external:
        # All rows must come from the same provider (one Excel file at a time).
        if len(external) > 1:
            raise HTTPException(
                status_code=400,
                detail=f"לא ניתן לייבא ביחד ספקים שונים: {sorted(external)}. "
                       f"בצע יבוא נפרד לכל קובץ.",
            )
        provider = next(iter(external))

        # SAFETY GATE — re-run dedup on the server side and refuse any
        # `create` action where match_level ∈ {exact_duplicate, strong}
        # UNLESS the row carries the explicit override flag _force_create=true.
        # The frontend sets _force_create only after the user types
        # "CREATE ANYWAY" in the confirmation modal.
        unsafe_rows: List[Dict[str, Any]] = []
        for r in payload.rows:
            if (r.get("_action") or "").lower() != "create":
                continue
            if r.get("_force_create") is True:
                continue
            verdict = find_matches(db, r)
            if verdict["match_level"] in UNSAFE_CREATE_LEVELS:
                unsafe_rows.append({
                    "source_row_number": r.get("source_row_number"),
                    "external_ref": (r.get("shipment_reference")
                                     or r.get("external_file_number")
                                     or r.get("external_job_number")),
                    "match_level": verdict["match_level"],
                    "match_score": verdict["match_score"],
                    "matched_shipment_reference": verdict["matched_shipment_reference"],
                })
        if unsafe_rows:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": (
                        f"חסום: {len(unsafe_rows)} שורות סומנו ליצירה אבל "
                        "מתאימות לכפילות מדויקת או חזקה. כדי להמשיך — "
                        "פתח כל שורה כזו ב-UI, בחר 'עדכן' או הקלד "
                        "CREATE ANYWAY כדי לכפות יצירה כפולה."
                    ),
                    "unsafe_rows": unsafe_rows,
                },
            )

        # Pick file/sheet from the first row (they should all match)
        sample = payload.rows[0]
        result = external_import_service.apply(
            db, payload.rows,
            actor_name=actor_name,
            source_provider=provider,
            source_file_name=sample.get("source_file_name"),
            source_sheet_name=sample.get("source_sheet_name"),
        )
        log.info("External import by %s: batch#%s — %s",
                 actor_name, result.get("batch_id"),
                 {k: v for k, v in result.items() if k != "per_row"})
        return result

    # Royal Linen template path (unchanged)
    result = excel_import_service.apply(db, payload.rows, actor_name=actor_name)
    log.info("Template import by %s: %s", actor_name, result)
    return result


# =====================================================================
# Import Batch list / details / rollback
# =====================================================================

@router.get("/batches")
def list_batches(
    limit: int = 100,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("shipment.read")),
):
    rows = (
        db.query(ImportBatch)
        .order_by(ImportBatch.id.desc())
        .limit(limit)
        .all()
    )
    return [{
        "id": b.id,
        "source_provider": b.source_provider,
        "source_file_name": b.source_file_name,
        "source_sheet_name": b.source_sheet_name,
        "imported_by": b.imported_by,
        "imported_at": b.imported_at.isoformat() if b.imported_at else None,
        "total_rows_in_preview": b.total_rows_in_preview,
        "created_count": b.created_count,
        "updated_count": b.updated_count,
        "skipped_count": b.skipped_count,
        "error_count": b.error_count,
        "status": b.status,
        "rolled_back_at": b.rolled_back_at.isoformat() if b.rolled_back_at else None,
        "rolled_back_by": b.rolled_back_by,
        "rolled_back_count": b.rolled_back_count,
        "notes": b.notes,
    } for b in rows]


@router.get("/batches/{batch_id}")
def batch_detail(
    batch_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("shipment.read")),
):
    b = db.query(ImportBatch).filter(ImportBatch.id == batch_id).first()
    if not b:
        raise HTTPException(status_code=404, detail="Batch not found")
    # Count live (non-archived) shipments still pointing to this batch
    live_shipments = db.query(Shipment).filter(
        Shipment.import_batch_id == batch_id,
        Shipment.archived == False,   # noqa: E712
    ).all()
    return {
        "id": b.id,
        "source_provider": b.source_provider,
        "source_file_name": b.source_file_name,
        "source_sheet_name": b.source_sheet_name,
        "imported_by": b.imported_by,
        "imported_at": b.imported_at.isoformat() if b.imported_at else None,
        "total_rows_in_preview": b.total_rows_in_preview,
        "created_count": b.created_count,
        "updated_count": b.updated_count,
        "skipped_count": b.skipped_count,
        "error_count": b.error_count,
        "status": b.status,
        "rolled_back_at": b.rolled_back_at.isoformat() if b.rolled_back_at else None,
        "rolled_back_by": b.rolled_back_by,
        "rolled_back_count": b.rolled_back_count,
        "rolled_back_reason": b.rolled_back_reason,
        "notes": b.notes,
        "details": b.details_json,
        "live_shipments": [
            {"id": s.id, "shp_id": s.shp_id, "supplier": s.supplier,
             "had_post_import_edits": bool(s.manual_overrides)}
            for s in live_shipments
        ],
    }


class RollbackRequest(BaseModel):
    confirm: str   # must be "ROLLBACK"
    reason: Optional[str] = None


@router.post("/batches/{batch_id}/rollback")
def rollback_batch(
    batch_id: int,
    payload: RollbackRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("shipment.archive")),
):
    """Archive every shipment CREATED by this batch.

    UPDATE actions are NOT auto-reverted (we'd need before/after JSON for
    every changed field). The user can edit those manually if needed.
    """
    if payload.confirm != "ROLLBACK":
        raise HTTPException(
            status_code=400,
            detail="rollback דורש אישור: שלח 'confirm': 'ROLLBACK'",
        )
    actor_name = actor.full_name or actor.username
    return external_import_service.rollback_batch(
        db, batch_id, actor_name=actor_name, reason=payload.reason,
    )
