from datetime import date, datetime
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException

from ..models import ExtraWorkTask, Shipment, Container
from ..schemas.extra_work import ExtraWorkCreate, ExtraWorkUpdate
from . import event_service, alert_service


WORK_TRACKED_FIELDS = [
    "work_type", "work_description", "responsible_party", "external_supplier_name",
    "work_status", "expected_start_date", "actual_start_date",
    "expected_end_date", "actual_end_date",
    "delay_status", "delay_reason",
    "ready_for_distribution_estimated_date", "ready_for_distribution_actual_date",
    "branch_entry_eta", "branch_entry_actual_date", "notes",
]


def enrich_task(t: ExtraWorkTask, db: Session) -> Dict[str, Any]:
    data = {c.name: getattr(t, c.name) for c in t.__table__.columns}
    s = db.query(Shipment).filter(Shipment.id == t.shipment_id).first()
    data["shp_id"] = s.shp_id if s else None
    data["supplier"] = s.supplier if s else None
    if t.container_id:
        c = db.query(Container).filter(Container.id == t.container_id).first()
        data["container_number"] = c.container_number if c else None
    else:
        data["container_number"] = None
    return data


def list_tasks(
    db: Session,
    *,
    open_only: Optional[bool] = None,
    delayed_only: Optional[bool] = None,
    shipment_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    q = db.query(ExtraWorkTask)
    if shipment_id:
        q = q.filter(ExtraWorkTask.shipment_id == shipment_id)
    if open_only:
        q = q.filter(ExtraWorkTask.work_status.notin_(["הסתיים", "בוטל"]))
    if delayed_only:
        q = q.filter(ExtraWorkTask.work_status == "מתעכב")
    items = q.order_by(ExtraWorkTask.id.desc()).all()
    return [enrich_task(t, db) for t in items]


def create_task(db: Session, payload: ExtraWorkCreate, *, created_by: str = "admin") -> ExtraWorkTask:
    shipment = db.query(Shipment).filter(Shipment.id == payload.shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    if not shipment.extra_work_required:
        # auto-flag the shipment when adding a task
        shipment.extra_work_required = True
        shipment.extra_work_defined_at = datetime.utcnow()
        shipment.extra_work_defined_by = created_by

    if payload.work_status == "מתעכב" and not payload.delay_reason:
        raise HTTPException(status_code=400, detail="עיכוב מחייב סיבת עיכוב")

    if not payload.work_type or not payload.responsible_party:
        # Already validated by Pydantic for required, but reinforce
        if not payload.work_type:
            raise HTTPException(status_code=400, detail="חובה להזין סוג עבודה")

    data = payload.model_dump(exclude_unset=True)
    t = ExtraWorkTask(created_by=created_by, updated_by=created_by, **data)
    db.add(t)
    db.flush()
    event_service.log_event(
        db,
        entity_type="extra_work",
        entity_id=t.id,
        action_type="create",
        new_value=t.work_type,
        changed_by=created_by,
        source="manual",
        note=f"נוספה תוספת עבודה למשלוח {shipment.shp_id}",
    )
    if not t.expected_end_date:
        alert_service.create_alert(
            db,
            alert_type="extra_work_missing_end_date",
            title="תוספת עבודה ללא תאריך סיום",
            severity="medium",
            extra_work_task_id=t.id,
            shipment_id=t.shipment_id,
        )
    db.commit()
    db.refresh(t)
    return t


def update_task(db: Session, task_id: int, payload: ExtraWorkUpdate, *, updated_by: str = "admin") -> ExtraWorkTask:
    t = db.query(ExtraWorkTask).filter(ExtraWorkTask.id == task_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Task not found")

    data = payload.model_dump(exclude_unset=True)

    new_status = data.get("work_status", t.work_status)
    new_reason = data.get("delay_reason", t.delay_reason)
    if new_status == "מתעכב" and not new_reason:
        raise HTTPException(status_code=400, detail="עיכוב מחייב סיבת עיכוב")

    old_snapshot = {f: getattr(t, f) for f in WORK_TRACKED_FIELDS}
    for k, v in data.items():
        if k == "updated_by":
            continue
        setattr(t, k, v)
    t.updated_by = updated_by

    new_snapshot = {f: getattr(t, f) for f in WORK_TRACKED_FIELDS}
    event_service.diff_and_log(
        db,
        entity_type="extra_work",
        entity_id=t.id,
        old_obj=old_snapshot,
        new_obj=new_snapshot,
        changed_by=updated_by,
    )

    # If expected_end_date changed by > 2 days
    old_e = old_snapshot.get("expected_end_date")
    new_e = new_snapshot.get("expected_end_date")
    if old_e and new_e and abs((new_e - old_e).days) > 2:
        alert_service.create_alert(
            db,
            alert_type="extra_work_end_date_changed",
            title="תאריך סיום תוספת עבודה השתנה",
            description=f"{old_e} → {new_e}",
            severity="high",
            extra_work_task_id=t.id,
            shipment_id=t.shipment_id,
        )
    if new_status == "מתעכב":
        alert_service.create_alert(
            db,
            alert_type="extra_work_delayed",
            title="תוספת עבודה מתעכבת",
            description=new_reason,
            severity="high",
            extra_work_task_id=t.id,
            shipment_id=t.shipment_id,
        )

    db.commit()
    db.refresh(t)
    return t


def complete_task(db: Session, task_id: int, *, completed_by: str = "admin") -> ExtraWorkTask:
    return update_task(
        db, task_id,
        ExtraWorkUpdate(work_status="הסתיים", actual_end_date=date.today(), updated_by=completed_by),
        updated_by=completed_by,
    )
