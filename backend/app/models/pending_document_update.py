"""Pending field-update suggestions extracted from documents.

Created when a document is classified + has an extracted field value
that conflicts with (or fills in) the linked shipment's data. The user
must explicitly approve before the shipment field is touched.

Never auto-applies. Approval is the only path that mutates the shipment.
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Text, JSON,
)

from ..database import Base


class PendingDocumentUpdate(Base):
    __tablename__ = "pending_document_updates"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, nullable=False, index=True)
    shipment_id = Column(Integer, nullable=True, index=True)
    field_name = Column(String, nullable=False)
    current_value = Column(Text, nullable=True)
    suggested_value = Column(Text, nullable=True)
    confidence_score = Column(Float, nullable=True)
    reason = Column(Text, nullable=True)
    status = Column(String, default="pending", nullable=False)
    # pending / approved / rejected / edited / superseded

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(String, nullable=True)
    resolution_note = Column(Text, nullable=True)
    extracted_from_json = Column(JSON, nullable=True)
