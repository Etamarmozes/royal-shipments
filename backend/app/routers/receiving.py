"""Warehouse receiving endpoints — used by the receiving page."""
from typing import Optional, List
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models import Container, Shipment, EmailAttachment
from ..services import receiving_service, container_service
from ..services.auth_service import require_permission
from ..models import User

router = APIRouter(prefix="/receiving", tags=["receiving"])


class ReceiveRequest(BaseModel):
    received_cartons_actual: Optional[int] = None
    received_pallets_actual: Optional[int] = None
    received_notes: Optional[str] = None
    received_by: Optional[str] = "warehouse"
    receiving_status: Optional[str] = None


@router.get("/queue")
def receiving_queue(db: Session = Depends(get_db)):
    """Containers expected at the warehouse — the warehouse receiving worklist.
    Includes documents available count for each."""
    # Note: SQL `IN (...)` does NOT match NULL, so we OR in `IS NULL` explicitly
    # — many seeded containers have receiving_status = NULL.
    rows = (
        db.query(Container)
        .options(joinedload(Container.shipment))
        .filter(
            or_(
                Container.receiving_status.in_(["not_received", "partially_received"]),
                Container.receiving_status.is_(None),
            )
        )
        .all()
    )
    out: List[dict] = []
    for c in rows:
        if c.shipment and c.shipment.archived:
            continue
        s = c.shipment
        eta = c.eta_warehouse or (s.eta_warehouse if s else None) \
            or c.eta_israel or (s.eta_israel if s else None)
        if not eta:
            continue
        docs_count = db.query(EmailAttachment).filter(
            EmailAttachment.linked_shipment_id == c.shipment_id
        ).count()
        out.append({
            **container_service.enrich_container(c),
            "eta_for_warehouse": eta.isoformat() if eta else None,
            "documents_count": docs_count,
        })
    out.sort(key=lambda d: d.get("eta_for_warehouse") or "9999")
    return out


@router.get("/container/{container_id}")
def container_receiving_view(container_id: int, db: Session = Depends(get_db)):
    """Everything the warehouse worker needs in one shot:
    container info + shipment + linked documents."""
    c = container_service.get_container(db, container_id)
    enriched = container_service.enrich_container(c)
    docs = db.query(EmailAttachment).filter(
        (EmailAttachment.linked_container_id == c.id)
        | (EmailAttachment.linked_shipment_id == c.shipment_id)
    ).all()
    enriched["documents"] = [
        {
            "id": d.id,
            "filename": d.filename,
            "document_type": d.document_type,
            "file_type": d.file_type,
            "linked_container_id": d.linked_container_id,
            "received_at": d.uploaded_at.isoformat() if d.uploaded_at else None,
        }
        for d in docs
    ]
    s = c.shipment
    if s:
        enriched["shipment_supplier"] = s.supplier
        enriched["shipment_goods"] = s.goods_description
        enriched["shipment_product_image_path"] = s.product_image_path
        enriched["shipment_category"] = s.category
    return enriched


@router.post("/container/{container_id}/receive")
def receive_container(
    container_id: int, payload: ReceiveRequest, db: Session = Depends(get_db),
    actor: User = Depends(require_permission("receiving.update")),
):
    # Always attribute to the authenticated user — ignore the request body's
    # received_by claim so warehouse staff can't impersonate someone else.
    actor_name = actor.full_name or actor.username
    c = receiving_service.receive_container(
        db, container_id,
        received_cartons_actual=payload.received_cartons_actual,
        received_pallets_actual=payload.received_pallets_actual,
        received_notes=payload.received_notes,
        received_by=actor_name,
        receiving_status=payload.receiving_status,
    )
    return container_service.enrich_container(c)
