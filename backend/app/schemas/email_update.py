from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, ConfigDict


class EmailAttachmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    filename: Optional[str] = None
    file_type: Optional[str] = None
    document_type: Optional[str] = None
    linked_shipment_id: Optional[int] = None
    linked_container_id: Optional[int] = None
    uploaded_at: Optional[datetime] = None


class EmailUpdateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email_message_id: Optional[str] = None
    email_thread_id: Optional[str] = None
    sender: Optional[str] = None
    subject: Optional[str] = None
    received_at: Optional[datetime] = None
    body_excerpt: Optional[str] = None
    full_body_text: Optional[str] = None
    attachment_names: Optional[Any] = None
    detected_shipment_id: Optional[int] = None
    detected_container_id: Optional[int] = None
    confidence_score: Optional[float] = None
    detected_fields_json: Optional[Any] = None
    detection_type: Optional[str] = None
    status: str
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    rejected_by: Optional[str] = None
    rejected_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    auto_applied: Optional[bool] = None
    needs_review: Optional[bool] = None
    review_reason: Optional[str] = None
    applied_fields_json: Optional[Any] = None
    flagged_fields_json: Optional[Any] = None

    detected_shp_id: Optional[str] = None
    attachments: List[EmailAttachmentRead] = []


class EmailUpdateApprove(BaseModel):
    approved_by: Optional[str] = "admin"
    note: Optional[str] = None


class EmailUpdateAssign(BaseModel):
    shipment_id: int
    approved_by: Optional[str] = "admin"


class EmailUpdateInject(BaseModel):
    """Manually inject a fake email for testing the parser/detector."""
    sender: str
    subject: str
    body: str
    received_at: Optional[datetime] = None
    attachment_names: Optional[List[str]] = None
