from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, JSON,
)
from sqlalchemy.orm import relationship

from ..database import Base


class EmailUpdate(Base):
    __tablename__ = "email_updates"

    id = Column(Integer, primary_key=True, index=True)
    email_message_id = Column(String, unique=True, index=True, nullable=True)
    email_thread_id = Column(String, index=True, nullable=True)

    sender = Column(String, nullable=True)
    subject = Column(String, nullable=True)
    received_at = Column(DateTime, nullable=True)
    body_excerpt = Column(Text, nullable=True)
    full_body_text = Column(Text, nullable=True)
    attachment_names = Column(JSON, nullable=True)

    detected_shipment_id = Column(Integer, ForeignKey("shipments.id"), nullable=True)
    detected_container_id = Column(Integer, ForeignKey("containers.id"), nullable=True)

    confidence_score = Column(Float, nullable=True)
    detected_fields_json = Column(JSON, nullable=True)
    detection_type = Column(String, nullable=True)  # update_existing/new_shipment/needs_review/irrelevant

    status = Column(String, default="pending")
    # pending/approved/rejected/needs_review/auto_applied/ignored/assigned

    approved_by = Column(String, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    rejected_by = Column(String, nullable=True)
    rejected_at = Column(DateTime, nullable=True)

    # Auto-update policy fields
    auto_applied = Column(Boolean, default=False)
    needs_review = Column(Boolean, default=False)
    review_reason = Column(Text, nullable=True)
    applied_fields_json = Column(JSON, nullable=True)   # what we wrote
    flagged_fields_json = Column(JSON, nullable=True)   # what we did NOT write

    created_at = Column(DateTime, default=datetime.utcnow)

    attachments = relationship(
        "EmailAttachment", back_populates="email_update", cascade="all, delete-orphan"
    )


class EmailAttachment(Base):
    __tablename__ = "email_attachments"

    id = Column(Integer, primary_key=True, index=True)
    email_update_id = Column(Integer, ForeignKey("email_updates.id"), nullable=False)

    filename = Column(String, nullable=True)
    file_type = Column(String, nullable=True)
    file_size = Column(Integer, nullable=True)
    file_path = Column(String, nullable=True)  # null until downloaded
    document_type = Column(String, nullable=True)  # invoice/packing_list/bol/booking/other

    # Source-specific identifiers (so we can re-fetch on demand)
    gmail_attachment_id = Column(String, nullable=True)
    drive_file_id = Column(String, nullable=True)
    source_url = Column(String, nullable=True)

    # PDF parsing result (populated after extraction + parse)
    extracted_text = Column(String, nullable=True)
    text_extraction_status = Column(String, nullable=True)  # ok / image_only / error / not_pdf
    parsed_fields_json = Column(String, nullable=True)  # JSON

    linked_shipment_id = Column(Integer, ForeignKey("shipments.id"), nullable=True)
    linked_container_id = Column(Integer, ForeignKey("containers.id"), nullable=True)

    uploaded_at = Column(DateTime, default=datetime.utcnow)

    # Soft-archive: when true, the row stays in the DB and the file stays on
    # disk (unless the user explicitly chose delete_file), but the attachment
    # is hidden from every listing endpoint and from shipment pages.
    archived = Column(Boolean, default=False, nullable=False)
    archived_at = Column(DateTime, nullable=True)
    archived_by = Column(String, nullable=True)
    archived_reason = Column(Text, nullable=True)
    archived_mode = Column(String, nullable=True)
    # 'archive_record_only' | 'archive_file' | 'delete_file'

    # ---- Document classification + intelligence ----
    # `classification` ∈ {
    #   "shipment_document"        - generic doc (catch-all for valid)
    #   "commercial_invoice"
    #   "packing_list"
    #   "bill_of_lading"           - generic BL (HBL or MBL unknown)
    #   "house_bill_of_lading"
    #   "master_bill_of_lading"
    #   "purchase_order"
    #   "customs_document"
    #   "delivery_note"
    #   "certificate"
    #   "product_image"            - real product photo (not a logo)
    #   "email_noise"              - logos, signatures, footer images, …
    #   "unknown_needs_review"
    # }
    classification = Column(String, nullable=True)
    classification_confidence = Column(Float, nullable=True)   # 0..1
    classification_reason = Column(Text, nullable=True)
    classified_at = Column(DateTime, nullable=True)
    is_email_noise = Column(Boolean, default=False, nullable=False)
    is_inline = Column(Boolean, default=False, nullable=False)
    width_px = Column(Integer, nullable=True)
    height_px = Column(Integer, nullable=True)

    # Field extraction (populated only when extraction_status == 'done')
    extraction_status = Column(String, nullable=True)
    # 'not_attempted' | 'pending' | 'done' | 'text_unavailable' | 'error'
    extracted_fields_json = Column(JSON, nullable=True)

    # Manual overrides — when user picks the type explicitly
    manually_classified_by = Column(String, nullable=True)
    manually_classified_at = Column(DateTime, nullable=True)

    email_update = relationship("EmailUpdate", back_populates="attachments")
