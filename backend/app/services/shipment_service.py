from datetime import date, datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException

from ..config import SHP_ID_PREFIX, SHP_ID_START, SHP_ID_PADDING
from ..models import Shipment, Container, ExtraWorkTask
from ..schemas.shipment import ShipmentCreate, ShipmentUpdate, ShipmentRead
from . import event_service, alert_service


SHIPMENT_TRACKED_FIELDS = [
    "supplier", "goods_description", "origin_country", "origin_port",
    "shipping_channel", "current_stage", "stage_status",
    "etd", "eta_israel", "eta_port", "eta_warehouse",
    "actual_arrival_israel", "actual_arrival_port", "actual_arrival_warehouse",
    "customs_broker", "booking_number", "bol_number", "invoice_number",
    "po_number", "freight_price_usd", "goods_value_usd",
    "paperwork_complete", "approval_status", "delay_status", "delay_reason",
    "extra_work_required", "extra_work_note", "notes",
    # Category is shown on shipments + containers and frequently edited.
    # It MUST be in this list — otherwise:
    #   1. category edits don't get an audit-log entry
    #   2. category edits don't get manual_override protection, so an
    #      email-driven update can later overwrite the user's choice.
    "category",
]


def next_shp_id(db: Session) -> str:
    """Generate next SHP-XXX id by scanning existing ids."""
    last = (
        db.query(Shipment)
        .filter(Shipment.shp_id.like(f"{SHP_ID_PREFIX}%"))
        .order_by(Shipment.id.desc())
        .first()
    )
    n = SHP_ID_START
    if last:
        try:
            num = int(last.shp_id.replace(SHP_ID_PREFIX, ""))
            n = max(num + 1, SHP_ID_START)
        except ValueError:
            pass
    return f"{SHP_ID_PREFIX}{str(n).zfill(SHP_ID_PADDING)}"


def compute_days_to_arrival(eta: Optional[date]) -> Optional[int]:
    if not eta:
        return None
    return (eta - date.today()).days


def enrich_shipment(s: Shipment) -> Dict[str, Any]:
    data = {c.name: getattr(s, c.name) for c in s.__table__.columns}
    data["days_to_arrival"] = compute_days_to_arrival(s.eta_israel)
    data["container_count"] = len(s.containers) if s.containers else 0
    data["has_open_extra_work"] = any(
        t.work_status not in ("הסתיים", "בוטל") for t in (s.extra_work_tasks or [])
    )
    return data


def list_shipments(
    db: Session,
    *,
    archived: Optional[bool] = False,
    search: Optional[str] = None,
    stage: Optional[int] = None,
    delay: Optional[bool] = None,
    customs_broker: Optional[str] = None,
    origin_country: Optional[str] = None,
    paperwork_missing: Optional[bool] = None,
    extra_work_only: Optional[bool] = None,
    category: Optional[str] = None,
    week_iso: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
) -> Dict[str, Any]:
    q = db.query(Shipment).options(
        joinedload(Shipment.containers),
        joinedload(Shipment.extra_work_tasks),
    )
    if archived is not None:
        q = q.filter(Shipment.archived == archived)
    if search:
        like = f"%{search}%"
        q = q.outerjoin(Container, Container.shipment_id == Shipment.id).filter(
            or_(
                Shipment.shp_id.ilike(like),
                Shipment.supplier.ilike(like),
                Shipment.goods_description.ilike(like),
                Shipment.booking_number.ilike(like),
                Shipment.bol_number.ilike(like),
                Container.container_number.ilike(like),
            )
        ).distinct()
    if stage is not None:
        q = q.filter(Shipment.current_stage == stage)
    if delay is not None:
        q = q.filter(Shipment.delay_status == delay)
    if customs_broker:
        q = q.filter(Shipment.customs_broker == customs_broker)
    if origin_country:
        q = q.filter(Shipment.origin_country == origin_country)
    if paperwork_missing is True:
        q = q.filter(Shipment.paperwork_complete == False)  # noqa: E712
    if extra_work_only is True:
        q = q.filter(Shipment.extra_work_required == True)  # noqa: E712
    if category:
        q = q.filter(Shipment.category == category)

    total = q.count()
    items = q.order_by(Shipment.id.desc()).offset(offset).limit(limit).all()

    return {
        "items": [enrich_shipment(s) for s in items],
        "total": total,
    }


def get_shipment(db: Session, shipment_id: int) -> Shipment:
    s = (
        db.query(Shipment)
        .options(joinedload(Shipment.containers), joinedload(Shipment.extra_work_tasks))
        .filter(Shipment.id == shipment_id)
        .first()
    )
    if not s:
        raise HTTPException(status_code=404, detail="Shipment not found")
    return s


def create_shipment(
    db: Session, payload: ShipmentCreate, *, created_by: str = "admin",
    creation_source: str = "manual", source_email_id: Optional[int] = None,
) -> Shipment:
    if payload.delay_status and not payload.delay_reason:
        raise HTTPException(status_code=400, detail="סטטוס עיכוב מחייב סיבת עיכוב")

    shp_id = next_shp_id(db)
    data = payload.model_dump(exclude_unset=True)
    data.pop("creation_source", None)
    s = Shipment(
        shp_id=shp_id,
        creation_source=creation_source,
        source_email_id=source_email_id,
        last_update_source=creation_source,
        updated_by=created_by,
        created_date=date.today(),
        **data,
    )
    if s.extra_work_required:
        s.extra_work_defined_at = datetime.utcnow()
        s.extra_work_defined_by = created_by
    db.add(s)
    db.flush()

    event_service.log_event(
        db,
        entity_type="shipment",
        entity_id=s.id,
        action_type="create",
        new_value=s.shp_id,
        changed_by=created_by,
        source=creation_source,
        note="נוצר משלוח חדש",
    )
    if s.paperwork_complete is False and (s.current_stage or 0) >= 5:
        alert_service.check_paperwork_for_stage(db, s)
    db.commit()
    db.refresh(s)
    return s


def update_shipment(
    db: Session, shipment_id: int, payload: ShipmentUpdate, *, updated_by: str = "admin",
    source: str = "manual",
) -> Shipment:
    s = get_shipment(db, shipment_id)
    data = payload.model_dump(exclude_unset=True)

    # Validation: delay reason required when delay_status set
    new_delay_status = data.get("delay_status", s.delay_status)
    new_delay_reason = data.get("delay_reason", s.delay_reason)
    if new_delay_status and not new_delay_reason:
        raise HTTPException(status_code=400, detail="סטטוס עיכוב מחייב סיבת עיכוב")

    old_snapshot = {f: getattr(s, f) for f in SHIPMENT_TRACKED_FIELDS}

    extra_was_required = s.extra_work_required

    for k, v in data.items():
        if k == "updated_by":
            continue
        setattr(s, k, v)
    s.updated_by = updated_by
    s.last_update_source = source

    if not extra_was_required and s.extra_work_required:
        s.extra_work_defined_at = datetime.utcnow()
        s.extra_work_defined_by = updated_by

    new_snapshot = {f: getattr(s, f) for f in SHIPMENT_TRACKED_FIELDS}

    # Manual-override tracking: if a user (not the email pipeline) changed a
    # tracked field, record it so future email auto-updates won't overwrite it.
    if source == "manual":
        overrides = dict(s.manual_overrides or {})
        now_iso = datetime.utcnow().isoformat()
        for f in SHIPMENT_TRACKED_FIELDS:
            if old_snapshot.get(f) != new_snapshot.get(f):
                overrides[f] = {"by": updated_by, "at": now_iso}
        if overrides != (s.manual_overrides or {}):
            s.manual_overrides = overrides

    event_service.diff_and_log(
        db,
        entity_type="shipment",
        entity_id=s.id,
        old_obj=old_snapshot,
        new_obj=new_snapshot,
        changed_by=updated_by,
        source=source,
    )

    # Trigger alerts on ETA changes
    for f in ("eta_israel", "eta_port", "eta_warehouse"):
        if f in data:
            alert_service.check_eta_change(
                db, s, f, old_snapshot.get(f), new_snapshot.get(f)
            )
    alert_service.check_paperwork_for_stage(db, s)

    db.commit()
    db.refresh(s)
    return s


def archive_shipment(db: Session, shipment_id: int, *, deleted_by: str = "admin") -> Shipment:
    """Alias for soft_delete_shipment — semantically clearer at call sites."""
    return soft_delete_shipment(db, shipment_id, deleted_by=deleted_by)


def soft_delete_shipment(db: Session, shipment_id: int, *, deleted_by: str = "admin") -> Shipment:
    s = get_shipment(db, shipment_id)
    s.archived = True
    s.completed_at = datetime.utcnow()
    s.updated_by = deleted_by
    event_service.log_event(
        db,
        entity_type="shipment",
        entity_id=s.id,
        action_type="archive",
        changed_by=deleted_by,
        source="manual",
        note="העברה לארכיון",
    )
    db.commit()
    db.refresh(s)
    return s
