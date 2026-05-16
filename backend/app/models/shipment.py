from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, Date, DateTime, Text, ForeignKey, JSON,
)
from sqlalchemy.orm import relationship

from ..database import Base


class Shipment(Base):
    __tablename__ = "shipments"

    id = Column(Integer, primary_key=True, index=True)
    shp_id = Column(String, unique=True, index=True, nullable=False)

    supplier = Column(String, nullable=True)
    goods_description = Column(Text, nullable=True)
    origin_country = Column(String, nullable=True)
    origin_port = Column(String, nullable=True)
    shipping_channel = Column(String, nullable=True)  # sea/air/other

    current_stage = Column(Integer, nullable=True)  # 1..9
    stage_status = Column(String, nullable=True)

    order_date = Column(Date, nullable=True)
    created_date = Column(Date, nullable=True)
    etd = Column(Date, nullable=True)
    eta_israel = Column(Date, nullable=True)
    eta_port = Column(Date, nullable=True)
    eta_warehouse = Column(Date, nullable=True)
    actual_arrival_israel = Column(Date, nullable=True)
    actual_arrival_port = Column(Date, nullable=True)
    actual_arrival_warehouse = Column(Date, nullable=True)
    days_to_arrival = Column(Integer, nullable=True)

    customs_broker = Column(String, nullable=True)
    booking_number = Column(String, nullable=True)
    bol_number = Column(String, nullable=True)
    invoice_number = Column(String, nullable=True)
    po_number = Column(String, nullable=True)

    freight_price_usd = Column(Float, nullable=True)
    goods_value_usd = Column(Float, nullable=True)

    paperwork_complete = Column(Boolean, default=False)
    approval_status = Column(String, nullable=True)  # ממתין/אושר/נדחה
    delay_status = Column(Boolean, default=False)
    delay_reason = Column(Text, nullable=True)

    notes = Column(Text, nullable=True)

    creation_source = Column(String, default="manual")  # manual/email_import/excel_import

    # Wider classification of data origin (set during import, free to edit
    # later). One of: demo / manual / excel / email / imported.
    # Distinguishes seed/demo from real data so we can safely delete demos.
    data_source = Column(String, nullable=True)

    # When true, this row is demo/test data. Bulk-delete operations and
    # data-review screens use this flag. Defaults to False (real data).
    is_test_data = Column(Boolean, default=False)

    source_email_id = Column(Integer, nullable=True)
    last_auto_update_source_email_id = Column(Integer, nullable=True)
    last_auto_update_at = Column(DateTime, nullable=True)
    product_image_path = Column(String, nullable=True)

    # Product category (free + controlled list managed in services/category_service)
    category = Column(String, nullable=True)
    category_source = Column(String, nullable=True)  # manual / email_auto / inferred

    extra_work_required = Column(Boolean, default=False)
    extra_work_defined_at = Column(DateTime, nullable=True)
    extra_work_defined_by = Column(String, nullable=True)
    extra_work_note = Column(Text, nullable=True)

    archived = Column(Boolean, default=False)
    completed_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = Column(String, nullable=True)
    last_update_source = Column(String, default="manual")  # manual/email/system

    # Per-field metadata: which fields were manually overridden + by whom + when.
    # Format: {"eta_israel": {"by": "alice", "at": "2026-05-03T12:00:00"}, ...}
    # Email auto-updates SKIP fields listed here (they create an alert instead).
    manual_overrides = Column(JSON, nullable=True)

    # ----- External-format import provenance (ICL / Eli Line) -----
    # Set ONLY when this shipment was created by an external-format
    # import. Used for traceability + rollback (archive all rows where
    # import_batch_id == X).
    import_batch_id = Column(Integer, nullable=True, index=True)
    source_provider = Column(String, nullable=True)
    source_file_name = Column(String, nullable=True)
    source_sheet_name = Column(String, nullable=True)
    source_row_number = Column(Integer, nullable=True)
    raw_source_json = Column(JSON, nullable=True)   # the full preview row, for audit

    # ----- External business identifiers -----
    external_file_number = Column(String, nullable=True)
    external_job_number = Column(String, nullable=True)
    sho_list = Column(String, nullable=True)
    customs_file_number = Column(String, nullable=True)
    house_bill_of_lading_number = Column(String, nullable=True)
    master_bill_of_lading_number = Column(String, nullable=True)
    vessel_name = Column(String, nullable=True)
    marks = Column(String, nullable=True)
    incoterm = Column(String, nullable=True)
    carrier = Column(String, nullable=True)
    destination_port = Column(String, nullable=True)
    product_description_raw = Column(Text, nullable=True)

    # ----- Inference (suggestion only) -----
    inferred_brand = Column(String, nullable=True)
    inferred_category = Column(String, nullable=True)
    inference_confidence = Column(Float, nullable=True)

    # ----- Container quantity at shipment level -----
    # ICL/Eli files give quantity+type, not actual container numbers.
    # We store quantity here AND optionally create placeholder Container
    # rows (with container_number=null) — the user picks via /apply.
    container_quantity = Column(Integer, nullable=True)
    container_quantity_raw = Column(String, nullable=True)
    container_quantity_confidence = Column(String, nullable=True)
    container_type_raw = Column(String, nullable=True)
    container_raw = Column(String, nullable=True)
    cbm_raw = Column(String, nullable=True)

    # ----- Review flag (separate from manual_overrides) -----
    needs_review = Column(Boolean, default=False, nullable=False)
    review_reason = Column(Text, nullable=True)

    containers = relationship(
        "Container", back_populates="shipment", cascade="all, delete-orphan"
    )
    extra_work_tasks = relationship(
        "ExtraWorkTask", back_populates="shipment", cascade="all, delete-orphan"
    )
