"""Document Assignment QC — endpoints.

  GET  /qc/documents                      List QC results (latest per doc).
  POST /qc/documents/run                  Trigger a fresh scan now.
  GET  /qc/documents/{result_id}          Detail incl. signals + reasons.
  POST /qc/documents/{result_id}/approve  Approve an action (keep / move /
                                          detach / mark_correct / ignore).
                                          ONLY this endpoint mutates
                                          `email_attachments.linked_shipment_id`.

  GET  /qc/rules                          List supplier/keyword rules.
  POST /qc/rules                          Create a new rule.
  PUT  /qc/rules/{id}                     Update.
  POST /qc/rules/{id}/deactivate          Disable.

  GET  /qc/summary                        Counters for the dashboard tile.
"""
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..config import UPLOADS_DIR
from ..database import get_db
from ..models import (
    DocumentAssignmentRule, DocumentAssignmentQcResult,
    DocumentAssignmentAction,
    EmailAttachment, Shipment, User,
)
from ..services import document_qc_service, event_service
from ..services.auth_service import require_permission

log = logging.getLogger("doc-qc")
ARCHIVE_DIR = UPLOADS_DIR / "documents" / "_archived"
ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

router = APIRouter(prefix="/qc", tags=["document-qc"])


# =====================================================================
# Results
# =====================================================================

@router.get("/documents")
def list_results(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """List QC results. Defaults to all open results (most recent per doc)."""
    q = db.query(DocumentAssignmentQcResult)
    if status:
        q = q.filter(DocumentAssignmentQcResult.status == status)
    else:
        q = q.filter(DocumentAssignmentQcResult.status == "open")
    if severity:
        q = q.filter(DocumentAssignmentQcResult.severity == severity)
    rows = q.order_by(DocumentAssignmentQcResult.confidence_score.asc(),
                       DocumentAssignmentQcResult.id.desc()).limit(500).all()

    # Enrich with attachment + shipment context for the UI
    out: List[Dict[str, Any]] = []
    for r in rows:
        att = db.query(EmailAttachment).filter(EmailAttachment.id == r.document_id).first()
        cur = db.query(Shipment).filter(Shipment.id == r.current_shipment_id).first() \
              if r.current_shipment_id else None
        sus = db.query(Shipment).filter(Shipment.id == r.suspected_shipment_id).first() \
              if r.suspected_shipment_id else None
        out.append({
            "id": r.id,
            "document_id": r.document_id,
            "filename": att.filename if att else None,
            "document_type": att.document_type if att else None,
            "current_shipment_id": r.current_shipment_id,
            "current_shp_id": cur.shp_id if cur else None,
            "current_supplier": cur.supplier if cur else None,
            "suspected_shipment_id": r.suspected_shipment_id,
            "suspected_shp_id": sus.shp_id if sus else None,
            "suspected_supplier": sus.supplier if sus else None,
            "confidence_score": r.confidence_score,
            "severity": r.severity,
            "status": r.status,
            "mismatch_reasons": r.mismatch_reasons_json or [],
            "matched_signals": r.matched_signals_json or [],
            "recommendation": r.recommendation,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "resolved_at": r.resolved_at.isoformat() if r.resolved_at else None,
            "resolved_by": r.resolved_by,
            "resolution_action": r.resolution_action,
        })
    return {"rows": out, "total": len(out)}


@router.get("/summary")
def summary(db: Session = Depends(get_db)):
    """Counters for the dashboard. Always answers — never errors."""
    open_total = db.query(DocumentAssignmentQcResult).filter(
        DocumentAssignmentQcResult.status == "open"
    ).count()
    open_strong = db.query(DocumentAssignmentQcResult).filter(
        DocumentAssignmentQcResult.status == "open",
        DocumentAssignmentQcResult.severity == "strong_mismatch",
    ).count()
    open_suspicious = db.query(DocumentAssignmentQcResult).filter(
        DocumentAssignmentQcResult.status == "open",
        DocumentAssignmentQcResult.severity == "suspicious",
    ).count()
    last_scan = db.query(DocumentAssignmentQcResult).order_by(
        DocumentAssignmentQcResult.created_at.desc()
    ).first()
    return {
        "open_total": open_total,
        "open_strong_mismatch": open_strong,
        "open_suspicious": open_suspicious,
        "last_scan_at": last_scan.created_at.isoformat() if last_scan and last_scan.created_at else None,
    }


@router.get("/documents/by-shipment/{shipment_id}")
def list_for_shipment(shipment_id: int, db: Session = Depends(get_db)):
    """Open QC results whose CURRENT shipment is this one — used by the
    'מסמכי מקור' tab to show the suspicious badge."""
    rows = db.query(DocumentAssignmentQcResult).filter(
        DocumentAssignmentQcResult.status == "open",
        DocumentAssignmentQcResult.current_shipment_id == shipment_id,
    ).all()
    return [{
        "id": r.id, "document_id": r.document_id,
        "severity": r.severity, "confidence_score": r.confidence_score,
        "suspected_shipment_id": r.suspected_shipment_id,
        "recommendation": r.recommendation,
        "mismatch_reasons": r.mismatch_reasons_json or [],
    } for r in rows]


@router.post("/documents/run")
def run_scan(
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("shipment.read")),
):
    """Trigger a fresh QC scan over every attachment.
    Read-only against `email_attachments`; writes only to QC tables."""
    summary = document_qc_service.run_scan(db)
    return summary


# =====================================================================
# Approval workflow — the ONLY mutator of linked_shipment_id from QC
# =====================================================================

class ApproveRequest(BaseModel):
    action: str = Field(..., pattern="^(keep|move|detach|mark_correct|needs_review|ignore)$")
    target_shipment_id: Optional[int] = None  # required for action=move
    reason: Optional[str] = None
    confirm: str  # must be "APPLY"


@router.post("/documents/{result_id}/approve")
def approve(
    result_id: int,
    payload: ApproveRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("document.assign")),
):
    """Apply a QC decision.

    Required body: `{"action": "...", "confirm": "APPLY"}` plus
    `target_shipment_id` when action="move".

    Actions:
      - keep            : record decision, close the result, no link change
      - move            : reassign to target_shipment_id
      - detach          : clear linked_shipment_id (keep the file)
      - mark_correct    : same as keep but flagged as user-verified
      - ignore          : close as a false positive

    Always logged in `document_assignment_actions` with before/after json.
    """
    if payload.confirm != "APPLY":
        raise HTTPException(
            status_code=400,
            detail="פעולה זו דורשת אישור: שלח 'confirm': 'APPLY'",
        )

    res = db.query(DocumentAssignmentQcResult).filter(
        DocumentAssignmentQcResult.id == result_id
    ).first()
    if not res:
        raise HTTPException(status_code=404, detail="QC result not found")
    if res.status != "open":
        raise HTTPException(status_code=400, detail=f"QC result already resolved: {res.status}")

    att = db.query(EmailAttachment).filter(EmailAttachment.id == res.document_id).first()
    if not att:
        raise HTTPException(status_code=404, detail="Document not found")

    before = {
        "linked_shipment_id": att.linked_shipment_id,
        "linked_container_id": att.linked_container_id,
    }
    new_shipment_id = att.linked_shipment_id   # default unchanged

    actor_name = actor.full_name or actor.username

    if payload.action == "move":
        if not payload.target_shipment_id:
            raise HTTPException(status_code=400, detail="target_shipment_id חובה לפעולה move")
        target = db.query(Shipment).filter(Shipment.id == payload.target_shipment_id).first()
        if not target:
            raise HTTPException(status_code=404, detail="Target shipment not found")
        att.linked_shipment_id = target.id
        # Container link no longer applies to a different shipment
        if att.linked_container_id:
            from ..models import Container
            c = db.query(Container).filter(Container.id == att.linked_container_id).first()
            if c and c.shipment_id != target.id:
                att.linked_container_id = None
        new_shipment_id = target.id
        res.status = "approved_move"
    elif payload.action == "detach":
        att.linked_shipment_id = None
        att.linked_container_id = None
        new_shipment_id = None
        res.status = "approved_detach"
    elif payload.action == "keep":
        res.status = "approved_keep"
    elif payload.action == "mark_correct":
        res.status = "approved_keep"
    elif payload.action == "ignore":
        res.status = "dismissed_false_positive"
    elif payload.action == "needs_review":
        # Keep the QC item OPEN — it just gets a "user touched" marker so
        # the operator can come back to it. Don't close, don't reassign.
        res.resolution_action = "needs_review"
        res.resolution_note = payload.reason
        res.resolved_by = actor_name
        # status stays "open" — early return so the unconditional code
        # at the bottom (which assumes a status change) doesn't run.
        # `after` doesn't exist in this branch — link is unchanged.
        db.add(DocumentAssignmentAction(
            document_id=att.id,
            old_shipment_id=before["linked_shipment_id"],
            new_shipment_id=before["linked_shipment_id"],   # unchanged
            action="needs_review",
            reason=payload.reason,
            approved_by=actor_name,
            qc_result_id=res.id,
            before_json=before,
            after_json=before,                              # same
        ))
        db.commit()
        return {
            "ok": True, "result_id": res.id, "document_id": att.id,
            "before": before, "after": before, "action": "needs_review",
        }

    res.resolved_at = datetime.utcnow()
    res.resolved_by = actor_name
    res.resolution_action = payload.action
    res.resolution_note = payload.reason

    after = {
        "linked_shipment_id": att.linked_shipment_id,
        "linked_container_id": att.linked_container_id,
    }

    # Audit row
    db.add(DocumentAssignmentAction(
        document_id=att.id,
        old_shipment_id=before["linked_shipment_id"],
        new_shipment_id=after["linked_shipment_id"],
        action=payload.action,
        reason=payload.reason,
        approved_by=actor_name,
        qc_result_id=res.id,
        before_json=before,
        after_json=after,
    ))

    # Also log to ShipmentEvent so it shows in the existing history tab
    event_service.log_event(
        db,
        entity_type="email_attachment", entity_id=att.id,
        action_type=f"qc_{payload.action}",
        old_value=str(before["linked_shipment_id"] or ""),
        new_value=str(after["linked_shipment_id"] or ""),
        changed_by=actor_name, source="qc_approval",
        note=payload.reason,
    )

    db.commit()
    db.refresh(att)

    return {
        "ok": True,
        "result_id": res.id,
        "document_id": att.id,
        "before": before,
        "after": after,
        "action": payload.action,
    }


# =====================================================================
# Archive — soft delete by default, optional file move/delete
# =====================================================================

class ArchiveRequest(BaseModel):
    mode: str = Field(..., pattern="^(archive_record_only|archive_file|delete_file)$")
    confirm: str   # must be "DELETE" for delete_file, "ARCHIVE" otherwise
    reason: Optional[str] = None


@router.post("/documents/{result_id}/archive")
def archive_document(
    result_id: int,
    payload: ArchiveRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("document.delete")),
):
    """Archive (soft-delete) a document record + optionally its file.

    Three modes:
      - archive_record_only : flag DB row as archived, file untouched
                              (default — safest)
      - archive_file        : move the file to /uploads/documents/_archived/
                              (still on disk, recoverable manually)
      - delete_file         : permanently rm the file. Requires confirm="DELETE".

    The DB row is NEVER deleted. We need it for the audit trail.
    """
    # Confirm string check
    if payload.mode == "delete_file":
        if payload.confirm != "DELETE":
            raise HTTPException(status_code=400,
                detail="מחיקת קובץ פיזי דורשת confirm='DELETE'")
    else:
        if payload.confirm != "ARCHIVE":
            raise HTTPException(status_code=400,
                detail="ארכוב דורש confirm='ARCHIVE'")

    res = db.query(DocumentAssignmentQcResult).filter(
        DocumentAssignmentQcResult.id == result_id
    ).first()
    if not res:
        raise HTTPException(status_code=404, detail="QC result not found")

    att = db.query(EmailAttachment).filter(EmailAttachment.id == res.document_id).first()
    if not att:
        raise HTTPException(status_code=404, detail="Document not found")

    actor_name = actor.full_name or actor.username
    before = {
        "linked_shipment_id": att.linked_shipment_id,
        "linked_container_id": att.linked_container_id,
        "file_path": att.file_path,
        "archived": bool(att.archived),
    }

    file_action = "no-op"
    file_on_disk = None
    if att.file_path:
        file_on_disk = (UPLOADS_DIR / "documents" / Path(att.file_path).name)

    if payload.mode == "archive_file" and file_on_disk and file_on_disk.exists():
        try:
            target = ARCHIVE_DIR / file_on_disk.name
            # Don't clobber if name collides
            if target.exists():
                stem, suf = target.stem, target.suffix
                target = ARCHIVE_DIR / f"{stem}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}{suf}"
            shutil.move(str(file_on_disk), str(target))
            att.file_path = f"_archived/{target.name}"
            file_action = f"moved_to_{target.name}"
            log.info("Archived file: doc#%s → %s", att.id, target)
        except Exception as e:
            log.exception("Archive move failed for doc#%s: %s", att.id, e)
            raise HTTPException(status_code=500, detail=f"שגיאה בארכוב הקובץ: {e}")

    elif payload.mode == "delete_file" and file_on_disk and file_on_disk.exists():
        try:
            file_on_disk.unlink()
            att.file_path = None
            file_action = "file_deleted"
            log.warning("Deleted file: doc#%s by %s", att.id, actor_name)
        except Exception as e:
            log.exception("Delete failed for doc#%s: %s", att.id, e)
            raise HTTPException(status_code=500, detail=f"שגיאה במחיקת הקובץ: {e}")

    # Always: mark archived, clear shipment links
    att.archived = True
    att.archived_at = datetime.utcnow()
    att.archived_by = actor_name
    att.archived_reason = payload.reason
    att.archived_mode = payload.mode
    # Detach from shipment so it stops appearing under /shipments/{id}/documents
    att.linked_shipment_id = None
    att.linked_container_id = None

    after = {
        "linked_shipment_id": None,
        "linked_container_id": None,
        "file_path": att.file_path,
        "archived": True,
        "file_action": file_action,
    }

    # Close the QC result
    res.status = "approved_detach"   # archived = effectively detached
    res.resolved_at = datetime.utcnow()
    res.resolved_by = actor_name
    res.resolution_action = f"archive:{payload.mode}"
    res.resolution_note = payload.reason

    # Audit
    db.add(DocumentAssignmentAction(
        document_id=att.id,
        old_shipment_id=before["linked_shipment_id"],
        new_shipment_id=None,
        action=f"archive_{payload.mode}",
        reason=payload.reason,
        approved_by=actor_name,
        qc_result_id=res.id,
        before_json=before,
        after_json=after,
    ))
    event_service.log_event(
        db,
        entity_type="email_attachment", entity_id=att.id,
        action_type=f"archive_{payload.mode}",
        old_value=str(before["linked_shipment_id"] or ""),
        new_value=f"archived ({file_action})",
        changed_by=actor_name, source="qc_archive",
        note=payload.reason,
    )

    db.commit()
    return {
        "ok": True,
        "result_id": res.id,
        "document_id": att.id,
        "mode": payload.mode,
        "file_action": file_action,
        "before": before,
        "after": after,
    }


# =====================================================================
# Rules
# =====================================================================

class RuleCreate(BaseModel):
    rule_name: str
    supplier_or_brand: str
    keywords: List[str]
    notes: Optional[str] = None


class RuleUpdate(BaseModel):
    rule_name: Optional[str] = None
    supplier_or_brand: Optional[str] = None
    keywords: Optional[List[str]] = None
    notes: Optional[str] = None
    active: Optional[bool] = None


@router.get("/rules")
def list_rules(db: Session = Depends(get_db)):
    rows = db.query(DocumentAssignmentRule).order_by(DocumentAssignmentRule.id).all()
    return [{
        "id": r.id, "rule_name": r.rule_name, "supplier_or_brand": r.supplier_or_brand,
        "keywords": r.keywords_json or [], "active": bool(r.active),
        "notes": r.notes,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    } for r in rows]


@router.post("/rules")
def create_rule(
    payload: RuleCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("users.manage")),
):
    if not payload.keywords:
        raise HTTPException(status_code=400, detail="לפחות מילת מפתח אחת")
    r = DocumentAssignmentRule(
        rule_name=payload.rule_name,
        supplier_or_brand=payload.supplier_or_brand,
        keywords_json=payload.keywords,
        active=True,
        notes=payload.notes,
        created_by=actor.full_name or actor.username,
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return {"id": r.id}


@router.put("/rules/{rule_id}")
def update_rule(
    rule_id: int,
    payload: RuleUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("users.manage")),
):
    r = db.query(DocumentAssignmentRule).filter(DocumentAssignmentRule.id == rule_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Rule not found")
    if payload.rule_name is not None: r.rule_name = payload.rule_name
    if payload.supplier_or_brand is not None: r.supplier_or_brand = payload.supplier_or_brand
    if payload.keywords is not None: r.keywords_json = payload.keywords
    if payload.notes is not None: r.notes = payload.notes
    if payload.active is not None: r.active = bool(payload.active)
    r.updated_at = datetime.utcnow()
    db.commit()
    return {"ok": True}


@router.post("/rules/{rule_id}/deactivate")
def deactivate_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("users.manage")),
):
    r = db.query(DocumentAssignmentRule).filter(DocumentAssignmentRule.id == rule_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Rule not found")
    r.active = False
    r.updated_at = datetime.utcnow()
    db.commit()
    return {"ok": True}
