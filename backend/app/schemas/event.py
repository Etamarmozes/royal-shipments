from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class ShipmentEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    entity_type: str
    entity_id: int
    action_type: str
    field_changed: Optional[str] = None
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    changed_by: Optional[str] = None
    changed_at: datetime
    source: str
    note: Optional[str] = None
