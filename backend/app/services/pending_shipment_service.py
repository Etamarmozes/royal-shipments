from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException

from ..models import (
    PendingShipment, PendingContainer, Shipment, Container, EmailUpdate,
)
from ..schemas.pending_shipment import PendingShipmentUpdate, PendingContainerUpdate
from ..schemas.shipment import ShipmentCreate
from . import shipment_service, event_service, alert_service


def list_pending(db: Session, *, status: Optional[str] = "pending"):
    q = db.query(PendingShipment).options(
        joinedload(PendingShipment.pending_containers),
    )
    if status:
        q = q.filter(PendingShipment.status == status)
    items = q.order_by(PendingShipment.id.desc()).all()
    out = []
    for ps in items:
        d = {c.name: getattr(ps, c.name) for c in ps.__table__.columns}
        d["pending_containers"] = [
            {col.name: getattr(pc, col.name) for col in pc.__table__.columns}
            for pc in ps.pending_containers
        ]
        if ps.source_email_update_id:
            eu = db.query(EmailUpdate).filter(
                EmailUpdate.id == ps.source_email_update_id
            ).first()
            if eu:
                d["sender"] = eu.sender
                d["subject"] = eu.subject
        out.append(d)
    return out


def get_pending(db: Session, pending_id: int) -> Dict[str, Any]:
    ps = db.query(PendingShipment).options(
        joinedload(PendingShipment.pending_containers),
    ).filter(PendingShipment.id == pending_id).first()
    if not ps:
        raise HTTPException(status_code=404, detail="Pending shipment not found")
    d = {c.name: getattr(ps, c.name) for c in ps.__table__.columns}
    d["pending_containers"] = [
        {col.name: getattr(pc, col.name) for col in pc.__table__.columns}
        for pc in ps.pending_containers
    ]
    if ps.source_email_update_id:
        eu = db.query(EmailUpdate).filter(
            EmailUpdate.id == ps.source_email_update_id
        ).first()
        if eu:
            d["sender"] = eu.sender
            d["subject"] = eu.subject
    return d


def update_pending(
    db: Session, pending_id: int, payload: PendingShipmentUpdate,
) -> PendingShipment:
    ps = db.query(PendingShipment).filter(PendingShipment.id == pending_id).first()
    if not ps:
        raise HTTPException(status_code=404, detail="Pending shipment not found")
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(ps, k, v)
    db.commit()
    db.refresh(ps)
    return ps


def update_pending_container(
    db: Session, pending_container_id: int, payload: PendingContainerUpdate,
) -> PendingContainer:
    pc = db.query(PendingContainer).filter(
        PendingContainer.id == pending_container_id
    ).first()
    if not pc:
        raise HTTPException(status_code=404, detail="Pending container not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(pc, k, v)
    db.commit()
    db.refresh(pc)
    return pc


def approve_pending(db: Session, pending_id: int, approved_by: str = "admin") -> Shipment:
    ps = db.query(PendingShipment).options(
        joinedload(PendingShipment.pending_containers),
    ).filter(PendingShipment.id == pending_id).first()
    if not ps:
        raise HTTPException(status_code=404, detail="Pending shipment not found")
    if ps.status != "pending":
        raise HTTPException(status_code=400, detail="טיוטה כבר טופלה")

    payload = ShipmentCreate(
        supplier=ps.detected_supplier,
        goods_description=ps.detected_goods_description,
        origin_country=ps.detected_origin_country,
        origin_port=ps.detected_origin_port,
        shipping_channel=ps.detected_shipping_channel,
        etd=ps.detected_etd,
        eta_israel=ps.detected_eta_israel,
        eta_port=ps.detected_eta_port,
        eta_warehouse=ps.detected_eta_warehouse,
        customs_broker=ps.detected_customs_broker,
        booking_number=ps.detected_booking_number,
        bol_number=ps.detected_bol_number,
        invoice_number=ps.detected_invoice_number,
        po_number=ps.detected_po_number,
        goods_value_usd=ps.detected_goods_value_usd,
        freight_price_usd=ps.detected_freight_price_usd,
        paperwork_complete=ps.detected_paperwork_complete or False,
        notes=ps.detected_notes,
        approval_status="ממתין לבדיקה",
        current_stage=1,
    )
    s = shipment_service.create_shipment(
        db, payload, created_by=approved_by, creation_source="email_import",
        source_email_id=ps.source_email_update_id,
    )

    for pc in ps.pending_containers:
        c = Container(
            shipment_id=s.id,
            container_number=pc.detected_container_number,
            container_type=pc.detected_container_type,
            cbm=pc.detected_cbm,
            boxes_total=pc.detected_boxes_total,
            gross_weight_kg=pc.detected_gross_weight_kg,
            eta_israel=pc.detected_eta_israel,
            eta_port=pc.detected_eta_port,
            eta_warehouse=pc.detected_eta_warehouse,
            notes=pc.detected_notes,
            updated_by=approved_by,
        )
        db.add(c)
    db.flush()

    ps.status = "approved"
    ps.approved_by = approved_by
    ps.approved_at = datetime.utcnow()

    if ps.source_email_update_id:
        eu = db.query(EmailUpdate).filter(EmailUpdate.id == ps.source_email_update_id).first()
        if eu:
            eu.status = "approved"
            eu.approved_by = approved_by
            eu.approved_at = datetime.utcnow()

    event_service.log_event(
        db,
        entity_type="pending_shipment",
        entity_id=ps.id,
        action_type="approve",
        new_value=s.shp_id,
        changed_by=approved_by,
        source="manual",
        note="טיוטת משלוח אושרה והפכה למשלוח פעיל",
    )
    db.commit()
    db.refresh(s)
    return s


def reject_pending(
    db: Session, pending_id: int, rejected_by: str = "admin",
    rejection_reason: Optional[str] = None,
) -> PendingShipment:
    ps = db.query(PendingShipment).filter(PendingShipment.id == pending_id).first()
    if not ps:
        raise HTTPException(status_code=404, detail="Pending shipment not found")
    ps.status = "rejected"
    ps.rejected_by = rejected_by
    ps.rejected_at = datetime.utcnow()
    ps.rejection_reason = rejection_reason

    if ps.source_email_update_id:
        eu = db.query(EmailUpdate).filter(EmailUpdate.id == ps.source_email_update_id).first()
        if eu:
            eu.status = "rejected"
            eu.rejected_by = rejected_by
            eu.rejected_at = datetime.utcnow()

    event_service.log_event(
        db,
        entity_type="pending_shipment",
        entity_id=ps.id,
        action_type="reject",
        changed_by=rejected_by,
        source="manual",
        note=rejection_reason or "טיוטה נדחתה",
    )
    db.commit()
    db.refresh(ps)
    return ps


def assign_to_existing(
    db: Session, pending_id: int, shipment_id: int, approved_by: str = "admin",
) -> PendingShipment:
    ps = db.query(PendingShipment).filter(PendingShipment.id == pending_id).first()
    if not ps:
        raise HTTPException(status_code=404, detail="Pending shipment not found")
    s = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Shipment not found")

    ps.status = "assigned_to_existing"
    ps.assigned_shipment_id = shipment_id
    ps.approved_by = approved_by
    ps.approved_at = datetime.utcnow()

    if ps.source_email_update_id:
        eu = db.query(EmailUpdate).filter(EmailUpdate.id == ps.source_email_update_id).first()
        if eu:
            eu.detected_shipment_id = shipment_id
            eu.detection_type = "update_existing"
            eu.status = "pending"

    event_service.log_event(
        db,
        entity_type="pending_shipment",
        entity_id=ps.id,
        action_type="assign_to_existing",
        new_value=s.shp_id,
        changed_by=approved_by,
        source="manual",
    )
    db.commit()
    db.refresh(ps)
    return ps
