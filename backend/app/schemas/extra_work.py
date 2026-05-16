from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class ExtraWorkBase(BaseModel):
    work_type: str
    work_description: Optional[str] = None
    responsible_party: Optional[str] = None
    external_supplier_name: Optional[str] = None

    work_status: Optional[str] = "לא התחיל"
    expected_start_date: Optional[date] = None
    actual_start_date: Optional[date] = None
    expected_end_date: Optional[date] = None
    actual_end_date: Optional[date] = None

    delay_status: Optional[bool] = False
    delay_reason: Optional[str] = None

    ready_for_distribution_estimated_date: Optional[date] = None
    ready_for_distribution_actual_date: Optional[date] = None
    branch_entry_eta: Optional[date] = None
    branch_entry_actual_date: Optional[date] = None

    notes: Optional[str] = None


class ExtraWorkCreate(ExtraWorkBase):
    shipment_id: int
    container_id: Optional[int] = None


class ExtraWorkUpdate(BaseModel):
    work_type: Optional[str] = None
    work_description: Optional[str] = None
    responsible_party: Optional[str] = None
    external_supplier_name: Optional[str] = None
    work_status: Optional[str] = None
    expected_start_date: Optional[date] = None
    actual_start_date: Optional[date] = None
    expected_end_date: Optional[date] = None
    actual_end_date: Optional[date] = None
    delay_status: Optional[bool] = None
    delay_reason: Optional[str] = None
    ready_for_distribution_estimated_date: Optional[date] = None
    ready_for_distribution_actual_date: Optional[date] = None
    branch_entry_eta: Optional[date] = None
    branch_entry_actual_date: Optional[date] = None
    notes: Optional[str] = None
    updated_by: Optional[str] = None


class ExtraWorkRead(ExtraWorkBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    shipment_id: int
    container_id: Optional[int] = None
    created_at: Optional[datetime] = None
    created_by: Optional[str] = None
    updated_at: Optional[datetime] = None
    updated_by: Optional[str] = None

    shp_id: Optional[str] = None
    supplier: Optional[str] = None
    container_number: Optional[str] = None
