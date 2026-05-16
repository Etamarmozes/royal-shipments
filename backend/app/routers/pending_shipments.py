from typing import Optional, List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas.pending_shipment import (
    PendingShipmentRead, PendingShipmentUpdate, PendingShipmentApprove,
    PendingShipmentAssign,
)
from ..schemas.shipment import ShipmentRead
from ..services import pending_shipment_service, shipment_service

router = APIRouter(prefix="/pending-shipments", tags=["pending-shipments"])


@router.get("", response_model=List[PendingShipmentRead])
def list_pending(
    status: Optional[str] = "pending", db: Session = Depends(get_db),
):
    return pending_shipment_service.list_pending(db, status=status)


@router.get("/{pending_id}", response_model=PendingShipmentRead)
def get_pending(pending_id: int, db: Session = Depends(get_db)):
    return pending_shipment_service.get_pending(db, pending_id)


@router.put("/{pending_id}", response_model=PendingShipmentRead)
def update_pending(
    pending_id: int, payload: PendingShipmentUpdate, db: Session = Depends(get_db)
):
    pending_shipment_service.update_pending(db, pending_id, payload)
    return pending_shipment_service.get_pending(db, pending_id)


@router.post("/{pending_id}/approve", response_model=ShipmentRead)
def approve_pending(
    pending_id: int, payload: PendingShipmentApprove, db: Session = Depends(get_db)
):
    s = pending_shipment_service.approve_pending(
        db, pending_id, approved_by=payload.approved_by
    )
    return shipment_service.enrich_shipment(s)


@router.post("/{pending_id}/reject", response_model=PendingShipmentRead)
def reject_pending(
    pending_id: int, payload: PendingShipmentApprove, db: Session = Depends(get_db)
):
    pending_shipment_service.reject_pending(
        db, pending_id, rejected_by=payload.approved_by, rejection_reason=payload.note,
    )
    return pending_shipment_service.get_pending(db, pending_id)


@router.post("/{pending_id}/assign-to-existing-shipment", response_model=PendingShipmentRead)
def assign_to_existing(
    pending_id: int, payload: PendingShipmentAssign, db: Session = Depends(get_db),
):
    pending_shipment_service.assign_to_existing(
        db, pending_id, payload.shipment_id, approved_by=payload.approved_by
    )
    return pending_shipment_service.get_pending(db, pending_id)
