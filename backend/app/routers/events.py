from typing import Optional, List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ShipmentEvent
from ..schemas.event import ShipmentEventRead

router = APIRouter(prefix="/events", tags=["events"])


@router.get("", response_model=List[ShipmentEventRead])
def list_events(
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    limit: int = 200,
    db: Session = Depends(get_db),
):
    q = db.query(ShipmentEvent)
    if entity_type:
        q = q.filter(ShipmentEvent.entity_type == entity_type)
    if entity_id:
        q = q.filter(ShipmentEvent.entity_id == entity_id)
    return q.order_by(ShipmentEvent.changed_at.desc()).limit(limit).all()
