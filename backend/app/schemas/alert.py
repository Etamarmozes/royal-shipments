from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class AlertRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    alert_type: str
    severity: str
    shipment_id: Optional[int] = None
    container_id: Optional[int] = None
    extra_work_task_id: Optional[int] = None
    email_update_id: Optional[int] = None
    pending_shipment_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    due_date: Optional[date] = None
    resolved: bool
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    shp_id: Optional[str] = None
