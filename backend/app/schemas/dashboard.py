from datetime import date, datetime
from typing import Optional, List, Any
from pydantic import BaseModel


class DashboardKpis(BaseModel):
    active_shipments: int
    total_containers_in_transit: int
    containers_arriving_this_week_israel: int
    containers_arriving_next_week_israel: int
    containers_at_port: int
    containers_to_warehouse: int
    delayed_shipments: int
    awaiting_approval: int
    paperwork_missing: int
    pending_new_shipments_from_email: int
    pending_email_updates: int
    auto_applied_email_updates_today: int = 0
    shipments_with_open_extra_work: int
    extra_work_delayed: int
    total_cbm_in_transit: float
    last_email_sync_at: Optional[datetime] = None


class ForecastWeek(BaseModel):
    week_index: int
    week_label: str
    week_start: date
    week_end: date
    containers_arriving_israel: int
    containers_arriving_port: int
    containers_arriving_warehouse: int
    cbm_total: float
    weight_total_kg: float
    boxes_total: int
    suppliers: List[str]
    load_status: str  # פנוי/רגיל/עמוס/חריג
    container_ids: List[int] = []


class ActionItem(BaseModel):
    type: str
    title: str
    count: int
    severity: str
    link: Optional[str] = None


class EmailSummary(BaseModel):
    pending_updates: int
    pending_new_shipments: int
    needs_review: int
    auto_applied_today: int
    last_sync_at: Optional[datetime] = None


class ExtraWorkSummary(BaseModel):
    open_tasks: int
    delayed_tasks: int
    completed_tasks: int
    by_type: Any
