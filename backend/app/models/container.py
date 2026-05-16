from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, Date, DateTime, Text, ForeignKey, JSON,
)
from sqlalchemy.orm import relationship

from ..database import Base


class Container(Base):
    __tablename__ = "containers"

    id = Column(Integer, primary_key=True, index=True)
    shipment_id = Column(Integer, ForeignKey("shipments.id"), nullable=False)

    container_number = Column(String, index=True, nullable=True)
    container_type = Column(String, nullable=True)  # 40HC/40HQ/20'/...
    cbm = Column(Float, nullable=True)
    boxes_total = Column(Integer, nullable=True)
    gross_weight_kg = Column(Float, nullable=True)

    container_status = Column(String, nullable=True)
    eta_israel = Column(Date, nullable=True)
    eta_port = Column(Date, nullable=True)
    eta_warehouse = Column(Date, nullable=True)
    actual_arrival_israel = Column(Date, nullable=True)
    actual_arrival_port = Column(Date, nullable=True)
    actual_arrival_warehouse = Column(Date, nullable=True)

    warehouse_readiness_status = Column(String, nullable=True)
    unloading_priority = Column(String, default="רגיל")  # רגיל / גבוה / דחוף

    extra_work_required = Column(Boolean, default=False)
    extra_work_note = Column(Text, nullable=True)

    # ----- Carton dimensions (cm) -----
    carton_length_cm = Column(Float, nullable=True)
    carton_width_cm = Column(Float, nullable=True)
    carton_height_cm = Column(Float, nullable=True)

    # ----- Pallet calculation fields -----
    # 'euro' / 'industrial' / 'auto'  (auto = pick whichever uses fewer pallets)
    pallet_type_preference = Column(String, default="auto")
    estimated_pallets_euro = Column(Integer, nullable=True)
    estimated_pallets_industrial = Column(Integer, nullable=True)
    recommended_pallet_type = Column(String, nullable=True)  # 'euro' / 'industrial'
    estimated_pallets_final = Column(Integer, nullable=True)
    pallet_calc_notes = Column(Text, nullable=True)

    # Per-container category override; falls back to Shipment.category
    category = Column(String, nullable=True)

    # ----- Warehouse receiving (Stage 8) -----
    received_cartons_actual = Column(Integer, nullable=True)
    received_pallets_actual = Column(Integer, nullable=True)
    received_notes = Column(Text, nullable=True)
    received_by = Column(String, nullable=True)
    received_at = Column(DateTime, nullable=True)
    receiving_status = Column(String, default="not_received")
    # not_received / partially_received / received / discrepancy

    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = Column(String, nullable=True)

    # Per-field manual-override metadata. See Shipment.manual_overrides for format.
    manual_overrides = Column(JSON, nullable=True)

    # ----- Placeholder support for external-format imports -----
    # ICL / Eli Line Excel files give us container quantity + type but NOT
    # actual container numbers. When the operator opts to create placeholder
    # rows, container_number stays null and these flags mark the row.
    placeholder_container = Column(Boolean, default=False, nullable=False)
    actual_container_number_missing = Column(Boolean, default=False, nullable=False)
    container_sequence = Column(Integer, nullable=True)
    container_raw = Column(String, nullable=True)
    import_batch_id = Column(Integer, nullable=True, index=True)
    source_row_number = Column(Integer, nullable=True)

    shipment = relationship("Shipment", back_populates="containers")
