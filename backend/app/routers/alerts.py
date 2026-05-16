from typing import Optional, List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Alert, Shipment
from ..schemas.alert import AlertRead
from ..services import alert_service

router = APIRouter(prefix="/alerts", tags=["alerts"])


def _enrich(a: Alert, db: Session):
    d = {c.name: getattr(a, c.name) for c in a.__table__.columns}
    if a.shipment_id:
        s = db.query(Shipment).filter(Shipment.id == a.shipment_id).first()
        d["shp_id"] = s.shp_id if s else None
    return d


@router.get("", response_model=List[AlertRead])
def list_alerts(
    resolved: Optional[bool] = None,
    severity: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(Alert)
    if resolved is not None:
        q = q.filter(Alert.resolved == resolved)
    if severity:
        q = q.filter(Alert.severity == severity)
    rows = q.order_by(Alert.id.desc()).all()
    return [_enrich(a, db) for a in rows]


@router.put("/{alert_id}/resolve", response_model=AlertRead)
def resolve(alert_id: int, db: Session = Depends(get_db)):
    a = alert_service.resolve_alert(db, alert_id)
    db.commit()
    return _enrich(a, db)


@router.post("/scan")
def scan(db: Session = Depends(get_db)):
    alert_service.scan_alerts(db)
    return {"ok": True}
