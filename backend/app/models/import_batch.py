"""Import batch — every approved Excel apply creates one row here.

Used for:
  1. provenance: every imported shipment carries `import_batch_id` so we
     can show "Imported from ICL file row 16, batch #42" in the UI.
  2. rollback: archiving the batch archives every shipment that this
     batch CREATED (UPDATEs are not auto-rolled-back).
  3. dashboard counters: how many imported today / which providers.

Additive only — never removes anything.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, Boolean

from ..database import Base


class ImportBatch(Base):
    __tablename__ = "import_batches"

    id = Column(Integer, primary_key=True, index=True)
    source_provider = Column(String, nullable=False)   # "ICL" / "Eli Line" / "Royal Linen Template"
    source_file_name = Column(String, nullable=True)
    source_sheet_name = Column(String, nullable=True)
    imported_by = Column(String, nullable=True)
    imported_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    total_rows_in_preview = Column(Integer, default=0)
    created_count = Column(Integer, default=0)
    updated_count = Column(Integer, default=0)
    skipped_count = Column(Integer, default=0)
    error_count = Column(Integer, default=0)

    # Rollback metadata — set on archive
    rolled_back_at = Column(DateTime, nullable=True)
    rolled_back_by = Column(String, nullable=True)
    rolled_back_reason = Column(Text, nullable=True)
    rolled_back_count = Column(Integer, default=0)
    status = Column(String, default="applied")
    # applied / partially_rolled_back / rolled_back

    notes = Column(Text, nullable=True)
    details_json = Column(JSON, nullable=True)
