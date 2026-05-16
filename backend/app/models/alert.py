from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, Date

from ..database import Base


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)

    alert_type = Column(String, nullable=False)
    severity = Column(String, default="medium")  # low/medium/high/critical

    shipment_id = Column(Integer, nullable=True)
    container_id = Column(Integer, nullable=True)
    extra_work_task_id = Column(Integer, nullable=True)
    email_update_id = Column(Integer, nullable=True)
    pending_shipment_id = Column(Integer, nullable=True)

    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    due_date = Column(Date, nullable=True)

    resolved = Column(Boolean, default=False)
    resolved_by = Column(String, nullable=True)
    resolved_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)
