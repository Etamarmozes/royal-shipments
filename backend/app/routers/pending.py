"""Unified /pending endpoints.

Two kinds of pending items live in two tables:
  - 'update'   → EmailUpdate (detected_shipment_id set; user approval applies
                 detected fields to the shipment)
  - 'shipment' → PendingShipment (user approval creates a new Shipment)

These endpoints are a thin facade: list everything that needs attention in
one place, and approve/reject by (kind, id).
"""
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models import EmailUpdate, PendingShipment, Shipment
from ..services import email_sync_service, pending_shipment_service, shipment_service
from ..services.auth_service import require_permission

router = APIRouter(prefix="/pending", tags=["pending"])
log = logging.getLogger("pending")


# Statuses considered "open" / awaiting user decision
_OPEN_EU_STATUSES = {"parsed", "pending", "needs_review"}
_OPEN_PS_STATUSES = {"pending"}

# Detection types of EUs that represent a real proposed action
_ACTIONABLE_DETECTION_TYPES = {"update", "delay"}


def _eu_to_pending_item(eu: EmailUpdate, db: Session) -> Dict[str, Any]:
    fields_json = eu.detected_fields_json or {}
    extracted = (
        fields_json.get("extracted_fields")
        if isinstance(fields_json, dict) else {}
    ) or {}
    summary = (
        fields_json.get("summary")
        if isinstance(fields_json, dict) else None
    )
    shp_id = None
    if eu.detected_shipment_id:
        s = db.query(Shipment).filter(Shipment.id == eu.detected_shipment_id).first()
        shp_id = s.shp_id if s else None
    return {
        "kind": "update",
        "id": eu.id,
        "detection_type": eu.detection_type,
        "confidence_score": eu.confidence_score,
        "status": eu.status,
        "sender": eu.sender,
        "subject": eu.subject,
        "received_at": eu.received_at.isoformat() if eu.received_at else None,
        "body_excerpt": eu.body_excerpt,
        "summary": summary,
        "extracted_fields": extracted,
        "shipment_id": eu.detected_shipment_id,
        "shp_id": shp_id,
        "created_at": eu.created_at.isoformat() if eu.created_at else None,
    }


def _ps_to_pending_item(ps: PendingShipment, db: Session) -> Dict[str, Any]:
    fields = ps.detected_fields_json or {}
    if isinstance(fields, dict) and "extracted_fields" in fields:
        fields = fields["extracted_fields"]
    sender = subject = None
    if ps.source_email_update_id:
        eu = db.query(EmailUpdate).filter(EmailUpdate.id == ps.source_email_update_id).first()
        if eu:
            sender = eu.sender
            subject = eu.subject
    return {
        "kind": "shipment",
        "id": ps.id,
        "detection_type": "new_shipment",
        "confidence_score": ps.confidence_score,
        "status": ps.status,
        "sender": sender,
        "subject": subject,
        "summary": f"משלוח חדש: {ps.detected_supplier or '?'} • {ps.detected_goods_description or ''}".strip(),
        "extracted_fields": fields if isinstance(fields, dict) else {},
        "shipment_id": None,
        "shp_id": None,
        "container_count": len(ps.pending_containers or []),
        "created_at": ps.created_at.isoformat() if ps.created_at else None,
        "raw": {
            "supplier": ps.detected_supplier,
            "goods_description": ps.detected_goods_description,
            "eta_israel": ps.detected_eta_israel.isoformat() if ps.detected_eta_israel else None,
            "eta_warehouse": ps.detected_eta_warehouse.isoformat() if ps.detected_eta_warehouse else None,
            "booking_number": ps.detected_booking_number,
            "bol_number": ps.detected_bol_number,
            "invoice_number": ps.detected_invoice_number,
            "po_number": ps.detected_po_number,
        },
    }


@router.get("")
def list_pending(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Combined list of pending updates + pending shipments."""
    eus = (
        db.query(EmailUpdate)
        .filter(
            EmailUpdate.status.in_(list(_OPEN_EU_STATUSES)),
            EmailUpdate.detection_type.in_(list(_ACTIONABLE_DETECTION_TYPES)),
            EmailUpdate.detected_shipment_id.isnot(None),
        )
        .order_by(EmailUpdate.id.desc())
        .all()
    )
    pss = (
        db.query(PendingShipment)
        .options(joinedload(PendingShipment.pending_containers))
        .filter(PendingShipment.status.in_(list(_OPEN_PS_STATUSES)))
        .order_by(PendingShipment.id.desc())
        .all()
    )
    items: List[Dict[str, Any]] = []
    items.extend(_eu_to_pending_item(eu, db) for eu in eus)
    items.extend(_ps_to_pending_item(ps, db) for ps in pss)
    return {
        "items": items,
        "counts": {
            "total": len(items),
            "updates": sum(1 for i in items if i["kind"] == "update"),
            "shipments": sum(1 for i in items if i["kind"] == "shipment"),
        },
    }


@router.post("/{kind}/{item_id}/approve",
              dependencies=[Depends(require_permission("pending.approve"))])
def approve(
    kind: str, item_id: int,
    approved_by: Optional[str] = "admin",
    db: Session = Depends(get_db),
):
    log.info("Pending APPROVE kind=%s id=%s by=%s", kind, item_id, approved_by)
    if kind == "update":
        eu = email_sync_service.approve_update(db, item_id, approved_by=approved_by)
        return {"kind": "update", "id": eu.id, "status": eu.status, "shipment_id": eu.detected_shipment_id}
    elif kind == "shipment":
        s = pending_shipment_service.approve_pending(db, item_id, approved_by=approved_by)
        return {"kind": "shipment", "id": item_id, "status": "approved", "new_shipment_id": s.id, "shp_id": s.shp_id}
    raise HTTPException(status_code=400, detail=f"Unknown pending kind: {kind!r}. Use 'update' or 'shipment'.")


@router.post("/{kind}/{item_id}/reject",
              dependencies=[Depends(require_permission("pending.reject"))])
def reject(
    kind: str, item_id: int,
    rejected_by: Optional[str] = "admin",
    note: Optional[str] = None,
    db: Session = Depends(get_db),
):
    log.info("Pending REJECT kind=%s id=%s by=%s", kind, item_id, rejected_by)
    if kind == "update":
        eu = email_sync_service.reject_update(db, item_id, rejected_by=rejected_by)
        return {"kind": "update", "id": eu.id, "status": eu.status}
    elif kind == "shipment":
        ps = pending_shipment_service.reject_pending(
            db, item_id, rejected_by=rejected_by, rejection_reason=note
        )
        return {"kind": "shipment", "id": ps.id, "status": ps.status}
    raise HTTPException(status_code=400, detail=f"Unknown pending kind: {kind!r}. Use 'update' or 'shipment'.")
