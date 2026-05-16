from datetime import date, datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict


class ShipmentBase(BaseModel):
    supplier: Optional[str] = None
    goods_description: Optional[str] = None
    origin_country: Optional[str] = None
    origin_port: Optional[str] = None
    shipping_channel: Optional[str] = None
    current_stage: Optional[int] = None
    stage_status: Optional[str] = None

    order_date: Optional[date] = None
    created_date: Optional[date] = None
    etd: Optional[date] = None
    eta_israel: Optional[date] = None
    eta_port: Optional[date] = None
    eta_warehouse: Optional[date] = None
    actual_arrival_israel: Optional[date] = None
    actual_arrival_port: Optional[date] = None
    actual_arrival_warehouse: Optional[date] = None

    customs_broker: Optional[str] = None
    booking_number: Optional[str] = None
    bol_number: Optional[str] = None
    invoice_number: Optional[str] = None
    po_number: Optional[str] = None

    freight_price_usd: Optional[float] = None
    goods_value_usd: Optional[float] = None

    paperwork_complete: Optional[bool] = False
    approval_status: Optional[str] = None
    delay_status: Optional[bool] = False
    delay_reason: Optional[str] = None
    notes: Optional[str] = None

    extra_work_required: Optional[bool] = False
    extra_work_note: Optional[str] = None

    category: Optional[str] = None
    category_source: Optional[str] = None


class ShipmentCreate(ShipmentBase):
    creation_source: Optional[str] = "manual"


class ShipmentUpdate(ShipmentBase):
    updated_by: Optional[str] = None


class ShipmentRead(ShipmentBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    shp_id: str
    days_to_arrival: Optional[int] = None
    creation_source: Optional[str] = None
    last_update_source: Optional[str] = None
    archived: bool = False
    completed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    updated_by: Optional[str] = None
    extra_work_defined_at: Optional[datetime] = None
    extra_work_defined_by: Optional[str] = None
    container_count: Optional[int] = 0
    has_open_extra_work: Optional[bool] = False
    product_image_path: Optional[str] = None
    last_auto_update_source_email_id: Optional[int] = None
    last_auto_update_at: Optional[datetime] = None
    manual_overrides: Optional[Dict[str, Any]] = None

    # External-format import provenance
    import_batch_id: Optional[int] = None
    source_provider: Optional[str] = None
    source_file_name: Optional[str] = None
    source_sheet_name: Optional[str] = None
    source_row_number: Optional[int] = None
    raw_source_json: Optional[Dict[str, Any]] = None
    data_source: Optional[str] = None
    is_test_data: Optional[bool] = None

    # External business identifiers
    external_file_number: Optional[str] = None
    external_job_number: Optional[str] = None
    sho_list: Optional[str] = None
    customs_file_number: Optional[str] = None
    house_bill_of_lading_number: Optional[str] = None
    master_bill_of_lading_number: Optional[str] = None
    vessel_name: Optional[str] = None
    marks: Optional[str] = None
    incoterm: Optional[str] = None
    carrier: Optional[str] = None
    destination_port: Optional[str] = None
    product_description_raw: Optional[str] = None

    # Inference
    inferred_brand: Optional[str] = None
    inferred_category: Optional[str] = None
    inference_confidence: Optional[float] = None

    # Container quantity at shipment level
    container_quantity: Optional[int] = None
    container_quantity_raw: Optional[str] = None
    container_quantity_confidence: Optional[str] = None
    container_type_raw: Optional[str] = None
    container_raw: Optional[str] = None
    cbm_raw: Optional[str] = None

    # Review flags
    needs_review: Optional[bool] = None
    review_reason: Optional[str] = None


class ShipmentList(BaseModel):
    items: List[ShipmentRead]
    total: int
