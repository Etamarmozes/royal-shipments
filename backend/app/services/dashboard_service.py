from datetime import date, timedelta
from typing import Dict, Any, List
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from ..models import (
    Shipment, Container, ExtraWorkTask, EmailUpdate, PendingShipment,
)
from .forecast_service import week_range


def _state_dir():
    from pathlib import Path
    from ..config import DATA_DIR
    p = DATA_DIR / "state"
    p.mkdir(exist_ok=True)
    return p


def get_last_email_sync():
    p = _state_dir() / "last_email_sync.txt"
    if not p.exists():
        return None
    from datetime import datetime
    try:
        return datetime.fromisoformat(p.read_text().strip())
    except Exception:
        return None


def set_last_email_sync():
    from datetime import datetime
    p = _state_dir() / "last_email_sync.txt"
    p.write_text(datetime.utcnow().isoformat())


def kpis(db: Session) -> Dict[str, Any]:
    today = date.today()
    this_week_start, this_week_end = week_range(0)
    next_week_start, next_week_end = week_range(1)

    active = db.query(Shipment).filter(Shipment.archived == False).all()  # noqa: E712
    active_count = len(active)

    containers = (
        db.query(Container).options(joinedload(Container.shipment)).all()
    )

    in_transit = 0
    arriving_this_week = 0
    arriving_next_week = 0
    at_port = 0
    to_warehouse = 0
    cbm_in_transit = 0.0

    for c in containers:
        s = c.shipment
        if s and s.archived:
            continue
        eta_il = c.eta_israel or (s.eta_israel if s else None)
        eta_wh = c.eta_warehouse or (s.eta_warehouse if s else None)
        if not c.actual_arrival_warehouse:
            in_transit += 1
            cbm_in_transit += c.cbm or 0
        if eta_il:
            if this_week_start <= eta_il <= this_week_end:
                arriving_this_week += 1
            if next_week_start <= eta_il <= next_week_end:
                arriving_next_week += 1
        # at_port: arrived at port but not yet at warehouse
        if c.actual_arrival_port and not c.actual_arrival_warehouse:
            at_port += 1
        # to_warehouse: has a warehouse ETA and hasn't arrived at warehouse yet
        if eta_wh and not c.actual_arrival_warehouse:
            to_warehouse += 1

    delayed = sum(1 for s in active if s.delay_status)
    awaiting_approval = sum(1 for s in active if s.approval_status == "ממתין")
    paperwork_missing = sum(1 for s in active if not s.paperwork_complete)

    pending_new = db.query(PendingShipment).filter(PendingShipment.status == "pending").count()
    pending_updates = db.query(EmailUpdate).filter(
        EmailUpdate.status.in_(["pending", "needs_review"])
    ).count()
    today_start = date.today()
    auto_applied_today = db.query(EmailUpdate).filter(
        EmailUpdate.auto_applied == True,  # noqa: E712
        func.date(EmailUpdate.created_at) == today_start,
    ).count()

    open_extra_work_shipments = sum(
        1 for s in active
        if any(t.work_status not in ("הסתיים", "בוטל") for t in s.extra_work_tasks)
    )
    extra_work_delayed = (
        db.query(ExtraWorkTask).filter(ExtraWorkTask.work_status == "מתעכב").count()
    )

    return {
        "active_shipments": active_count,
        "total_containers_in_transit": in_transit,
        "containers_arriving_this_week_israel": arriving_this_week,
        "containers_arriving_next_week_israel": arriving_next_week,
        "containers_at_port": at_port,
        "containers_to_warehouse": to_warehouse,
        "delayed_shipments": delayed,
        "awaiting_approval": awaiting_approval,
        "paperwork_missing": paperwork_missing,
        "pending_new_shipments_from_email": pending_new,
        "pending_email_updates": pending_updates,
        "auto_applied_email_updates_today": auto_applied_today,
        "shipments_with_open_extra_work": open_extra_work_shipments,
        "extra_work_delayed": extra_work_delayed,
        "total_cbm_in_transit": round(cbm_in_transit, 2),
        "last_email_sync_at": get_last_email_sync(),
    }


def action_items(db: Session) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []

    pending_new = db.query(PendingShipment).filter(PendingShipment.status == "pending").count()
    if pending_new:
        items.append({
            "type": "pending_new",
            "title": "טיוטות משלוחים חדשים לאישור",
            "count": pending_new,
            "severity": "high",
            "link": "/pending-shipments",
        })

    pending_updates = db.query(EmailUpdate).filter(
        EmailUpdate.status == "pending"
    ).count()
    if pending_updates:
        items.append({
            "type": "pending_email_updates",
            "title": "עדכוני ETA / נתונים ממייל לאישור",
            "count": pending_updates,
            "severity": "medium",
            "link": "/email-updates",
        })

    needs_review = db.query(EmailUpdate).filter(
        EmailUpdate.status == "needs_review"
    ).count()
    if needs_review:
        items.append({
            "type": "email_needs_review",
            "title": "מיילים שדורשים שיוך ידני",
            "count": needs_review,
            "severity": "medium",
            "link": "/email-updates",
        })

    delays_no_reason = db.query(Shipment).filter(
        Shipment.delay_status == True,  # noqa: E712
        (Shipment.delay_reason.is_(None)) | (Shipment.delay_reason == ""),
        Shipment.archived == False,  # noqa: E712
    ).count()
    if delays_no_reason:
        items.append({
            "type": "delay_no_reason",
            "title": "עיכובים ללא סיבה",
            "count": delays_no_reason,
            "severity": "high",
            "link": "/shipments?delay=1",
        })

    paperwork_missing = db.query(Shipment).filter(
        Shipment.paperwork_complete == False,  # noqa: E712
        Shipment.archived == False,  # noqa: E712
        Shipment.current_stage >= 5,
    ).count()
    if paperwork_missing:
        items.append({
            "type": "paperwork_missing",
            "title": "ניירת חסרה במשלוחים בשלב מתקדם",
            "count": paperwork_missing,
            "severity": "high",
            "link": "/shipments?paperwork_missing=1",
        })

    return items


def email_summary(db: Session) -> Dict[str, Any]:
    pending_updates = db.query(EmailUpdate).filter(
        EmailUpdate.status == "pending",
        EmailUpdate.detection_type == "update_existing",
    ).count()
    pending_new = db.query(PendingShipment).filter(
        PendingShipment.status == "pending"
    ).count()
    needs_review = db.query(EmailUpdate).filter(
        EmailUpdate.status == "needs_review"
    ).count()
    today_start = date.today()
    auto_today = db.query(EmailUpdate).filter(
        EmailUpdate.status == "auto_applied",
        func.date(EmailUpdate.created_at) == today_start,
    ).count()
    return {
        "pending_updates": pending_updates,
        "pending_new_shipments": pending_new,
        "needs_review": needs_review,
        "auto_applied_today": auto_today,
        "last_sync_at": get_last_email_sync(),
    }


def extra_work_summary(db: Session) -> Dict[str, Any]:
    rows = db.query(ExtraWorkTask).all()
    open_tasks = sum(1 for t in rows if t.work_status not in ("הסתיים", "בוטל"))
    delayed_tasks = sum(1 for t in rows if t.work_status == "מתעכב")
    completed = sum(1 for t in rows if t.work_status == "הסתיים")
    by_type: Dict[str, int] = {}
    for t in rows:
        by_type[t.work_type] = by_type.get(t.work_type, 0) + 1
    return {
        "open_tasks": open_tasks,
        "delayed_tasks": delayed_tasks,
        "completed_tasks": completed,
        "by_type": by_type,
    }
