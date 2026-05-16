from datetime import date, datetime
from typing import Optional, List, Any
from pydantic import BaseModel, ConfigDict


class PendingContainerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    pending_shipment_id: int
    detected_container_number: Optional[str] = None
    detected_container_type: Optional[str] = None
    detected_cbm: Optional[float] = None
    detected_boxes_total: Optional[int] = None
    detected_gross_weight_kg: Optional[float] = None
    detected_eta_israel: Optional[date] = None
    detected_eta_port: Optional[date] = None
    detected_eta_warehouse: Optional[date] = None
    detected_notes: Optional[str] = None
    created_at: Optional[datetime] = None


class PendingContainerUpdate(BaseModel):
    detected_container_number: Optional[str] = None
    detected_container_type: Optional[str] = None
    detected_cbm: Optional[float] = None
    detected_boxes_total: Optional[int] = None
    detected_gross_weight_kg: Optional[float] = None
    detected_eta_israel: Optional[date] = None
    detected_eta_port: Optional[date] = None
    detected_eta_warehouse: Optional[date] = None
    detected_notes: Optional[str] = None


class PendingShipmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    source_email_update_id: Optional[int] = None
    detected_supplier: Optional[str] = None
    detected_goods_description: Optional[str] = None
    detected_origin_country: Optional[str] = None
    detected_origin_port: Optional[str] = None
    detected_shipping_channel: Optional[str] = None
    detected_etd: Optional[date] = None
    detected_eta_israel: Optional[date] = None
    detected_eta_port: Optional[date] = None
    detected_eta_warehouse: Optional[date] = None
    detected_customs_broker: Optional[str] = None
    detected_booking_number: Optional[str] = None
    detected_bol_number: Optional[str] = None
    detected_invoice_number: Optional[str] = None
    detected_po_number: Optional[str] = None
    detected_goods_value_usd: Optional[float] = None
    detected_freight_price_usd: Optional[float] = None
    detected_paperwork_complete: Optional[bool] = None
    detected_notes: Optional[str] = None
    confidence_score: Optional[float] = None
    missing_fields_json: Optional[Any] = None
    detected_fields_json: Optional[Any] = None
    status: str
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    rejected_by: Optional[str] = None
    rejected_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    assigned_shipment_id: Optional[int] = None
    created_at: Optional[datetime] = None

    sender: Optional[str] = None
    subject: Optional[str] = None
    pending_containers: List[PendingContainerRead] = []


class PendingShipmentUpdate(BaseModel):
    detected_supplier: Optional[str] = None
    detected_goods_description: Optional[str] = None
    detected_origin_country: Optional[str] = None
    detected_origin_port: Optional[str] = None
    detected_shipping_channel: Optional[str] = None
    detected_etd: Optional[date] = None
    detected_eta_israel: Optional[date] = None
    detected_eta_port: Optional[date] = None
    detected_eta_warehouse: Optional[date] = None
    detected_customs_broker: Optional[str] = None
    detected_booking_number: Optional[str] = None
    detected_bol_number: Optional[str] = None
    detected_invoice_number: Optional[str] = None
    detected_po_number: Optional[str] = None
    detected_goods_value_usd: Optional[float] = None
    detected_freight_price_usd: Optional[float] = None
    detected_paperwork_complete: Optional[bool] = None
    detected_notes: Optional[str] = None


class PendingShipmentApprove(BaseModel):
    approved_by: Optional[str] = "admin"
    note: Optional[str] = None


class PendingShipmentAssign(BaseModel):
    shipment_id: int
    approved_by: Optional[str] = "admin"
