from typing import Optional, Any
from sqlalchemy.orm import Session

from ..models import ShipmentEvent


def _stringify(v: Any) -> Optional[str]:
    if v is None:
        return None
    return str(v)


def log_event(
    db: Session,
    *,
    entity_type: str,
    entity_id: int,
    action_type: str,
    field_changed: Optional[str] = None,
    old_value: Any = None,
    new_value: Any = None,
    changed_by: Optional[str] = "admin",
    source: str = "manual",
    note: Optional[str] = None,
) -> ShipmentEvent:
    event = ShipmentEvent(
        entity_type=entity_type,
        entity_id=entity_id,
        action_type=action_type,
        field_changed=field_changed,
        old_value=_stringify(old_value),
        new_value=_stringify(new_value),
        changed_by=changed_by,
        source=source,
        note=note,
    )
    db.add(event)
    db.flush()
    return event


def diff_and_log(
    db: Session,
    *,
    entity_type: str,
    entity_id: int,
    old_obj: dict,
    new_obj: dict,
    changed_by: Optional[str] = "admin",
    source: str = "manual",
    fields: Optional[list] = None,
):
    """Compare two dicts (old/new), log a ShipmentEvent for each changed field."""
    keys = fields or list(set(old_obj.keys()) | set(new_obj.keys()))
    for key in keys:
        old_v = old_obj.get(key)
        new_v = new_obj.get(key)
        if old_v != new_v:
            log_event(
                db,
                entity_type=entity_type,
                entity_id=entity_id,
                action_type="update",
                field_changed=key,
                old_value=old_v,
                new_value=new_v,
                changed_by=changed_by,
                source=source,
            )
