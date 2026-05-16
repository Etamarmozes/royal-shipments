from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, Date, DateTime, Text, ForeignKey, JSON,
)
from sqlalchemy.orm import relationship

from ..database import Base


class PendingShipment(Base):
    __tablename__ = "pending_shipments"

    id = Column(Integer, primary_key=True, index=True)
    source_email_update_id = Column(Integer, ForeignKey("email_updates.id"), nullable=True)

    detected_supplier = Column(String, nullable=True)
    detected_goods_description = Column(Text, nullable=True)
    detected_origin_country = Column(String, nullable=True)
    detected_origin_port = Column(String, nullable=True)
    detected_shipping_channel = Column(String, nullable=True)

    detected_etd = Column(Date, nullable=True)
    detected_eta_israel = Column(Date, nullable=True)
    detected_eta_port = Column(Date, nullable=True)
    detected_eta_warehouse = Column(Date, nullable=True)

    detected_customs_broker = Column(String, nullable=True)
    detected_booking_number = Column(String, nullable=True)
    detected_bol_number = Column(String, nullable=True)
    detected_invoice_number = Column(String, nullable=True)
    detected_po_number = Column(String, nullable=True)

    detected_goods_value_usd = Column(Float, nullable=True)
    detected_freight_price_usd = Column(Float, nullable=True)
    detected_paperwork_complete = Column(Boolean, nullable=True)
    detected_notes = Column(Text, nullable=True)

    confidence_score = Column(Float, nullable=True)
    missing_fields_json = Column(JSON, nullable=True)
    detected_fields_json = Column(JSON, nullable=True)

    status = Column(String, default="pending")
    # pending/approved/rejected/assigned_to_existing

    approved_by = Column(String, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    rejected_by = Column(String, nullable=True)
    rejected_at = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    assigned_shipment_id = Column(Integer, ForeignKey("shipments.id"), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    pending_containers = relationship(
        "PendingContainer", back_populates="pending_shipment", cascade="all, delete-orphan"
    )


class PendingContainer(Base):
    __tablename__ = "pending_containers"

    id = Column(Integer, primary_key=True, index=True)
    pending_shipment_id = Column(Integer, ForeignKey("pending_shipments.id"), nullable=False)

    detected_container_number = Column(String, nullable=True)
    detected_container_type = Column(String, nullable=True)
    detected_cbm = Column(Float, nullable=True)
    detected_boxes_total = Column(Integer, nullable=True)
    detected_gross_weight_kg = Column(Float, nullable=True)
    detected_eta_israel = Column(Date, nullable=True)
    detected_eta_port = Column(Date, nullable=True)
    detected_eta_warehouse = Column(Date, nullable=True)
    detected_notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    pending_shipment = relationship("PendingShipment", back_populates="pending_containers")
