from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Boolean, Date, DateTime, Text, ForeignKey,
)
from sqlalchemy.orm import relationship

from ..database import Base


class ExtraWorkTask(Base):
    __tablename__ = "extra_work_tasks"

    id = Column(Integer, primary_key=True, index=True)
    shipment_id = Column(Integer, ForeignKey("shipments.id"), nullable=False)
    container_id = Column(Integer, ForeignKey("containers.id"), nullable=True)

    work_type = Column(String, nullable=False)
    work_description = Column(Text, nullable=True)
    responsible_party = Column(String, nullable=True)
    external_supplier_name = Column(String, nullable=True)

    work_status = Column(String, default="לא התחיל")
    expected_start_date = Column(Date, nullable=True)
    actual_start_date = Column(Date, nullable=True)
    expected_end_date = Column(Date, nullable=True)
    actual_end_date = Column(Date, nullable=True)

    delay_status = Column(Boolean, default=False)
    delay_reason = Column(Text, nullable=True)

    ready_for_distribution_estimated_date = Column(Date, nullable=True)
    ready_for_distribution_actual_date = Column(Date, nullable=True)

    branch_entry_eta = Column(Date, nullable=True)
    branch_entry_actual_date = Column(Date, nullable=True)

    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = Column(String, nullable=True)

    shipment = relationship("Shipment", back_populates="extra_work_tasks")
