from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text

from ..database import Base


class ShipmentEvent(Base):
    __tablename__ = "shipment_events"

    id = Column(Integer, primary_key=True, index=True)

    entity_type = Column(String, nullable=False)
    # shipment/container/extra_work/email_update/pending_shipment
    entity_id = Column(Integer, nullable=False)

    action_type = Column(String, nullable=False)
    field_changed = Column(String, nullable=True)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)

    changed_by = Column(String, nullable=True)
    changed_at = Column(DateTime, default=datetime.utcnow, index=True)
    source = Column(String, default="manual")  # manual/email_import/system

    note = Column(Text, nullable=True)
