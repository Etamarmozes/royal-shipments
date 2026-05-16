from datetime import date, datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, ConfigDict


class ContainerBase(BaseModel):
    container_number: Optional[str] = None
    container_type: Optional[str] = None
    cbm: Optional[float] = None
    boxes_total: Optional[int] = None
    gross_weight_kg: Optional[float] = None
    container_status: Optional[str] = None

    eta_israel: Optional[date] = None
    eta_port: Optional[date] = None
    eta_warehouse: Optional[date] = None
    actual_arrival_israel: Optional[date] = None
    actual_arrival_port: Optional[date] = None
    actual_arrival_warehouse: Optional[date] = None

    warehouse_readiness_status: Optional[str] = None
    unloading_priority: Optional[str] = "רגיל"

    extra_work_required: Optional[bool] = False
    extra_work_note: Optional[str] = None
    notes: Optional[str] = None

    # Carton dimensions (cm)
    carton_length_cm: Optional[float] = None
    carton_width_cm: Optional[float] = None
    carton_height_cm: Optional[float] = None

    # Pallet preference: 'euro' / 'industrial' / 'auto'
    pallet_type_preference: Optional[str] = "auto"

    # Category override (falls back to shipment.category)
    category: Optional[str] = None

    # Warehouse receiving
    received_cartons_actual: Optional[int] = None
    received_pallets_actual: Optional[int] = None
    received_notes: Optional[str] = None
    received_by: Optional[str] = None
    received_at: Optional[datetime] = None
    receiving_status: Optional[str] = None


class ContainerCreate(ContainerBase):
    shipment_id: int


class ContainerUpdate(ContainerBase):
    updated_by: Optional[str] = None


class ContainerRead(ContainerBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    shipment_id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    updated_by: Optional[str] = None

    # context fields populated by service
    shipment_shp_id: Optional[str] = None
    supplier: Optional[str] = None
    goods_description: Optional[str] = None
    effective_eta_israel: Optional[date] = None
    effective_eta_warehouse: Optional[date] = None

    # Pallet calc results (populated by pallet_service)
    estimated_pallets_euro: Optional[int] = None
    estimated_pallets_industrial: Optional[int] = None
    recommended_pallet_type: Optional[str] = None
    estimated_pallets_final: Optional[int] = None
    pallet_calc_notes: Optional[str] = None

    # Effective category (own or inherited from shipment)
    effective_category: Optional[str] = None

    # Per-field manual override metadata
    manual_overrides: Optional[Dict[str, Any]] = None
