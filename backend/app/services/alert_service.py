from datetime import date, datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from ..models import (
    Alert, Shipment, Container, ExtraWorkTask, EmailUpdate, PendingShipment,
)


def create_alert(
    db: Session,
    *,
    alert_type: str,
    title: str,
    description: Optional[str] = None,
    severity: str = "medium",
    shipment_id: Optional[int] = None,
    container_id: Optional[int] = None,
    extra_work_task_id: Optional[int] = None,
    email_update_id: Optional[int] = None,
    pending_shipment_id: Optional[int] = None,
    due_date: Optional[date] = None,
    dedupe: bool = True,
) -> Alert:
    """Create alert; with dedupe=True, won't recreate an existing open alert
    of the same type for the same entity."""
    if dedupe:
        q = db.query(Alert).filter(
            Alert.alert_type == alert_type,
            Alert.resolved == False,  # noqa: E712
        )
        if shipment_id is not None:
            q = q.filter(Alert.shipment_id == shipment_id)
        if container_id is not None:
            q = q.filter(Alert.container_id == container_id)
        if extra_work_task_id is not None:
            q = q.filter(Alert.extra_work_task_id == extra_work_task_id)
        if email_update_id is not None:
            q = q.filter(Alert.email_update_id == email_update_id)
        if pending_shipment_id is not None:
            q = q.filter(Alert.pending_shipment_id == pending_shipment_id)
        existing = q.first()
        if existing:
            return existing

    alert = Alert(
        alert_type=alert_type,
        title=title,
        description=description,
        severity=severity,
        shipment_id=shipment_id,
        container_id=container_id,
        extra_work_task_id=extra_work_task_id,
        email_update_id=email_update_id,
        pending_shipment_id=pending_shipment_id,
        due_date=due_date,
    )
    db.add(alert)
    db.flush()
    return alert


def resolve_alert(db: Session, alert_id: int, resolved_by: str = "admin") -> Optional[Alert]:
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        return None
    alert.resolved = True
    alert.resolved_by = resolved_by
    alert.resolved_at = datetime.utcnow()
    db.flush()
    return alert


def check_eta_change(
    db: Session, shipment: Shipment, field: str, old_value: Optional[date], new_value: Optional[date]
):
    """If ETA changed by more than 3 days, raise alert."""
    if old_value and new_value and abs((new_value - old_value).days) > 3:
        create_alert(
            db,
            alert_type=f"eta_changed_{field}",
            title=f"שינוי {field} ביותר מ-3 ימים — {shipment.shp_id}",
            description=f"{old_value} → {new_value}",
            severity="high",
            shipment_id=shipment.id,
        )


def check_paperwork_for_stage(db: Session, shipment: Shipment):
    if (
        shipment.paperwork_complete is False
        and shipment.current_stage is not None
        and shipment.current_stage >= 5
    ):
        create_alert(
            db,
            alert_type="paperwork_missing_late_stage",
            title=f"ניירת חסרה — {shipment.shp_id}",
            description=f"שלב נוכחי: {shipment.current_stage}",
            severity="high",
            shipment_id=shipment.id,
        )


def check_delay_requires_reason(shipment_or_task) -> Optional[str]:
    if getattr(shipment_or_task, "delay_status", False) and not getattr(
        shipment_or_task, "delay_reason", None
    ):
        return "סטטוס עיכוב מחייב סיבת עיכוב"
    return None


def scan_missing_documents(db: Session) -> int:
    """For every active shipment past stage 5, alert if Packing List / Invoice / BL is missing."""
    from . import document_service

    created = 0
    rows = db.query(Shipment).filter(
        Shipment.archived == False,  # noqa: E712
        Shipment.current_stage >= 5,
    ).all()
    LABEL = {
        "packing_list": "Packing List",
        "invoice": "Invoice",
        "bl": "BL/BOL/Booking",
    }
    for s in rows:
        status = document_service.required_documents_status(db, s)
        for missing in status["missing"]:
            create_alert(
                db,
                alert_type=f"missing_document_{missing}",
                title=f"חסר {LABEL[missing]} — {s.shp_id}",
                description=f"לא קיים {LABEL[missing]} עבור {s.shp_id}",
                severity="medium",
                shipment_id=s.id,
                dedupe=True,
            )
            created += 1
    db.commit()
    return created


def scan_alerts(db: Session):
    """Periodic scan for system-wide alert conditions."""
    today = date.today()
    in_seven = today + timedelta(days=7)

    # Container arrives within 7 days but unclear status
    containers = (
        db.query(Container)
        .filter(
            and_(
                Container.eta_israel.isnot(None),
                Container.eta_israel <= in_seven,
                Container.eta_israel >= today,
                or_(Container.container_status.is_(None), Container.container_status == ""),
            )
        )
        .all()
    )
    for c in containers:
        create_alert(
            db,
            alert_type="container_arriving_soon_unclear",
            title=f"מכולה מגיעה תוך 7 ימים — {c.container_number or c.id}",
            description="אין סטטוס ברור למכולה",
            severity="medium",
            container_id=c.id,
            shipment_id=c.shipment_id,
            due_date=c.eta_israel,
        )

    # Pending shipments
    pendings = db.query(PendingShipment).filter(PendingShipment.status == "pending").all()
    for ps in pendings:
        create_alert(
            db,
            alert_type="pending_shipment_awaiting_approval",
            title="טיוטת משלוח חדש ממתינה לאישור",
            description=f"ספק: {ps.detected_supplier or 'לא זוהה'}",
            severity="high",
            pending_shipment_id=ps.id,
        )

    # Pending email updates
    updates = (
        db.query(EmailUpdate)
        .filter(EmailUpdate.status.in_(["pending", "needs_review"]))
        .all()
    )
    for u in updates:
        if u.detection_type == "new_shipment":
            continue
        create_alert(
            db,
            alert_type="email_update_awaiting_approval",
            title="עדכון ממייל ממתין לאישור",
            description=u.subject or "",
            severity="medium" if u.status == "pending" else "high",
            email_update_id=u.id,
            shipment_id=u.detected_shipment_id,
        )

    # Late-stage paperwork missing
    late_no_paper = (
        db.query(Shipment)
        .filter(
            Shipment.paperwork_complete == False,  # noqa: E712
            Shipment.current_stage >= 5,
            Shipment.archived == False,  # noqa: E712
        )
        .all()
    )
    for s in late_no_paper:
        check_paperwork_for_stage(db, s)

    # Missing documents (Packing List / Invoice / BL)
    scan_missing_documents(db)

    # Extra work delayed / missing end date
    open_tasks = db.query(ExtraWorkTask).filter(
        ExtraWorkTask.work_status.notin_(["הסתיים", "בוטל"])
    ).all()
    for t in open_tasks:
        if t.work_status == "מתעכב":
            create_alert(
                db,
                alert_type="extra_work_delayed",
                title="תוספת עבודה מתעכבת",
                description=t.delay_reason or "",
                severity="high",
                extra_work_task_id=t.id,
                shipment_id=t.shipment_id,
            )
        if t.expected_end_date is None:
            create_alert(
                db,
                alert_type="extra_work_missing_end_date",
                title="תוספת עבודה ללא תאריך סיום צפוי",
                severity="medium",
                extra_work_task_id=t.id,
                shipment_id=t.shipment_id,
            )

    db.commit()
