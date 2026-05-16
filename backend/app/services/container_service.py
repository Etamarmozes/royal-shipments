from datetime import date
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_
from fastapi import HTTPException

from ..models import Container, Shipment
from ..schemas.container import ContainerCreate, ContainerUpdate
from . import event_service, alert_service, pallet_service


CONTAINER_TRACKED_FIELDS = [
    "container_number", "container_type", "cbm", "boxes_total",
    "gross_weight_kg", "container_status",
    "eta_israel", "eta_port", "eta_warehouse",
    "actual_arrival_israel", "actual_arrival_port", "actual_arrival_warehouse",
    "warehouse_readiness_status", "unloading_priority",
    "extra_work_required", "extra_work_note", "notes",
    "carton_length_cm", "carton_width_cm", "carton_height_cm",
    "pallet_type_preference",
]

# Fields that trigger automatic pallet recalculation when changed
PALLET_INPUT_FIELDS = {
    "carton_length_cm", "carton_width_cm", "carton_height_cm",
    "boxes_total", "cbm", "pallet_type_preference",
}


def effective_eta(container: Container, shipment: Optional[Shipment], field: str) -> Optional[date]:
    val = getattr(container, field, None)
    if val:
        return val
    if shipment:
        return getattr(shipment, field, None)
    return None


def enrich_container(c: Container) -> Dict[str, Any]:
    data = {col.name: getattr(c, col.name) for col in c.__table__.columns}
    s = c.shipment
    data["shipment_shp_id"] = s.shp_id if s else None
    data["supplier"] = s.supplier if s else None
    data["goods_description"] = s.goods_description if s else None
    data["effective_eta_israel"] = effective_eta(c, s, "eta_israel")
    data["effective_eta_warehouse"] = effective_eta(c, s, "eta_warehouse")
    # Effective category: container override → shipment default
    data["effective_category"] = c.category or (s.category if s else None)
    return data


def list_containers(
    db: Session,
    *,
    search: Optional[str] = None,
    status: Optional[str] = None,
    supplier: Optional[str] = None,
    extra_work_only: Optional[bool] = None,
    limit: int = 500,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    q = db.query(Container).options(joinedload(Container.shipment))
    if search:
        like = f"%{search}%"
        q = q.outerjoin(Shipment).filter(
            or_(
                Container.container_number.ilike(like),
                Shipment.shp_id.ilike(like),
                Shipment.supplier.ilike(like),
            )
        )
    if status:
        q = q.filter(Container.container_status == status)
    if supplier:
        q = q.outerjoin(Shipment).filter(Shipment.supplier == supplier)
    if extra_work_only:
        q = q.filter(Container.extra_work_required == True)  # noqa: E712

    items = q.order_by(Container.id.desc()).offset(offset).limit(limit).all()
    return [enrich_container(c) for c in items]


def get_container(db: Session, container_id: int) -> Container:
    c = (
        db.query(Container)
        .options(joinedload(Container.shipment))
        .filter(Container.id == container_id)
        .first()
    )
    if not c:
        raise HTTPException(status_code=404, detail="Container not found")
    return c


def create_container(
    db: Session, payload: ContainerCreate, *, created_by: str = "admin",
) -> Container:
    shipment = db.query(Shipment).filter(Shipment.id == payload.shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    data = payload.model_dump(exclude_unset=True)
    c = Container(updated_by=created_by, **data)
    db.add(c)
    db.flush()
    # Compute pallets from initial inputs (falls back to CBM if dims missing)
    pallet_service.apply_to_container(c)
    db.flush()
    event_service.log_event(
        db,
        entity_type="container",
        entity_id=c.id,
        action_type="create",
        new_value=c.container_number,
        changed_by=created_by,
        source="manual",
        note=f"נוספה מכולה למשלוח {shipment.shp_id}",
    )
    db.commit()
    db.refresh(c)
    return c


def update_container(
    db: Session, container_id: int, payload: ContainerUpdate, *, updated_by: str = "admin",
    source: str = "manual",
) -> Container:
    from datetime import datetime as _dt
    c = get_container(db, container_id)
    data = payload.model_dump(exclude_unset=True)

    old_snapshot = {f: getattr(c, f) for f in CONTAINER_TRACKED_FIELDS}
    for k, v in data.items():
        if k == "updated_by":
            continue
        setattr(c, k, v)
    c.updated_by = updated_by

    new_snapshot = {f: getattr(c, f) for f in CONTAINER_TRACKED_FIELDS}

    # Manual-override tracking — see shipment_service.update_shipment
    if source == "manual":
        overrides = dict(c.manual_overrides or {})
        now_iso = _dt.utcnow().isoformat()
        for f in CONTAINER_TRACKED_FIELDS:
            if old_snapshot.get(f) != new_snapshot.get(f):
                overrides[f] = {"by": updated_by, "at": now_iso}
        if overrides != (c.manual_overrides or {}):
            c.manual_overrides = overrides

    event_service.diff_and_log(
        db,
        entity_type="container",
        entity_id=c.id,
        old_obj=old_snapshot,
        new_obj=new_snapshot,
        changed_by=updated_by,
        source=source,
    )

    # Recompute pallets if any pallet-input field changed
    changed_inputs = {k for k in data if k in PALLET_INPUT_FIELDS}
    if changed_inputs:
        pallet_service.apply_to_container(c)
        db.flush()

    # ETA change alerts
    for f in ("eta_israel", "eta_port", "eta_warehouse"):
        if f in data:
            old_v = old_snapshot.get(f)
            new_v = new_snapshot.get(f)
            if old_v and new_v and abs((new_v - old_v).days) > 3:
                alert_service.create_alert(
                    db,
                    alert_type=f"container_{f}_changed",
                    title=f"שינוי {f} מכולה {c.container_number}",
                    description=f"{old_v} → {new_v}",
                    severity="high",
                    container_id=c.id,
                    shipment_id=c.shipment_id,
                )

    db.commit()
    db.refresh(c)
    return c


def recalculate_pallets(db: Session, container_id: int) -> Container:
    """Force recalculation of pallet estimates for a single container."""
    c = get_container(db, container_id)
    pallet_service.apply_to_container(c)
    db.commit()
    db.refresh(c)
    return c


def delete_container(db: Session, container_id: int, *, deleted_by: str = "admin"):
    c = get_container(db, container_id)
    event_service.log_event(
        db,
        entity_type="container",
        entity_id=c.id,
        action_type="delete",
        old_value=c.container_number,
        changed_by=deleted_by,
        source="manual",
    )
    db.delete(c)
    db.commit()
