from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models import EmailUpdate, Shipment
from ..schemas.email_update import (
    EmailUpdateRead, EmailUpdateApprove, EmailUpdateAssign, EmailUpdateInject,
)
from ..services import email_sync_service
from ..services.auth_service import require_permission

router = APIRouter(prefix="/email", tags=["email"])


def _enrich(eu: EmailUpdate, db: Session):
    d = {c.name: getattr(eu, c.name) for c in eu.__table__.columns}
    if eu.detected_shipment_id:
        s = db.query(Shipment).filter(Shipment.id == eu.detected_shipment_id).first()
        d["detected_shp_id"] = s.shp_id if s else None
    d["attachments"] = [
        {col.name: getattr(a, col.name) for col in a.__table__.columns}
        for a in eu.attachments
    ]
    return d


@router.post("/sync-now",
              dependencies=[Depends(require_permission("gmail.sync"))])
def sync_now(db: Session = Depends(get_db)):
    return email_sync_service.sync_now(db)


@router.post("/process-fetched",
              dependencies=[Depends(require_permission("email.process"))])
def process_fetched(db: Session = Depends(get_db)):
    """Run classification on every email currently in status='fetched'.

    This is the post-Gmail-sync step that turns raw emails into
    update_existing / new_shipment / irrelevant + creates PendingShipments
    and alerts where appropriate.
    """
    return email_sync_service.process_fetched_emails(db)


@router.put("/updates/{update_id}/reprocess", response_model=EmailUpdateRead)
def reprocess(update_id: int, db: Session = Depends(get_db)):
    """Re-run classification on a single existing EmailUpdate. Useful after
    fixing the parser, or after the user manually adjusts data."""
    eu = db.query(EmailUpdate).filter(EmailUpdate.id == update_id).first()
    if not eu:
        raise HTTPException(status_code=404, detail="Email update not found")
    email_sync_service.classify_email(db, eu)
    db.commit()
    db.refresh(eu)
    return _enrich(eu, db)


@router.post("/inject", response_model=EmailUpdateRead)
def inject_email(payload: EmailUpdateInject, db: Session = Depends(get_db)):
    """Manually inject a fake email for testing the parser/detector."""
    eu = email_sync_service.process_email(
        db,
        sender=payload.sender,
        subject=payload.subject,
        body=payload.body,
        received_at=payload.received_at,
        attachment_names=payload.attachment_names,
    )
    return _enrich(eu, db)


@router.get("/updates", response_model=List[EmailUpdateRead])
def list_email_updates(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(EmailUpdate).options(joinedload(EmailUpdate.attachments))
    if status:
        q = q.filter(EmailUpdate.status == status)
    rows = q.order_by(EmailUpdate.id.desc()).limit(500).all()
    return [_enrich(u, db) for u in rows]


@router.get("/updates/{update_id}", response_model=EmailUpdateRead)
def get_email_update(update_id: int, db: Session = Depends(get_db)):
    eu = (
        db.query(EmailUpdate)
        .options(joinedload(EmailUpdate.attachments))
        .filter(EmailUpdate.id == update_id)
        .first()
    )
    if not eu:
        raise HTTPException(status_code=404, detail="Not found")
    return _enrich(eu, db)


@router.put("/updates/{update_id}/approve", response_model=EmailUpdateRead,
             dependencies=[Depends(require_permission("email.approve"))])
def approve_update(
    update_id: int, payload: EmailUpdateApprove, db: Session = Depends(get_db),
):
    eu = email_sync_service.approve_update(db, update_id, approved_by=payload.approved_by)
    return _enrich(eu, db)


@router.put("/updates/{update_id}/reject", response_model=EmailUpdateRead,
             dependencies=[Depends(require_permission("email.reject"))])
def reject_update(
    update_id: int, payload: EmailUpdateApprove, db: Session = Depends(get_db),
):
    eu = email_sync_service.reject_update(db, update_id, rejected_by=payload.approved_by)
    return _enrich(eu, db)


@router.put("/updates/{update_id}/assign-shipment", response_model=EmailUpdateRead,
             dependencies=[Depends(require_permission("email.approve"))])
def assign_shipment(
    update_id: int, payload: EmailUpdateAssign, db: Session = Depends(get_db),
):
    eu = email_sync_service.assign_update(
        db, update_id, payload.shipment_id, approved_by=payload.approved_by
    )
    return _enrich(eu, db)
