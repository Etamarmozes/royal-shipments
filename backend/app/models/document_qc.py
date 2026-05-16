"""Document Assignment QC — three additive tables.

These tables exist to detect and audit document-to-shipment assignment
mistakes. They never modify existing shipment / attachment rows themselves
— only the existing /documents/{id}/assign endpoint mutates assignments,
and only via explicit user approval routed through this QC layer.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, JSON

from ..database import Base


class DocumentAssignmentRule(Base):
    """Configurable supplier/brand keyword rule.

    Each rule has a canonical supplier_or_brand name and a list of keywords
    (case-insensitive substring match). When a document's filename, email
    subject, sender, or body contains any of the keywords, that's evidence
    the document belongs to a shipment whose supplier contains the same
    name/keyword.
    """
    __tablename__ = "document_assignment_rules"

    id = Column(Integer, primary_key=True, index=True)
    rule_name = Column(String, nullable=False)              # display name
    supplier_or_brand = Column(String, nullable=False)      # canonical
    keywords_json = Column(JSON, nullable=False, default=list)
    active = Column(Boolean, default=True, nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(String, nullable=True)


class DocumentAssignmentQcResult(Base):
    """Per-attachment QC verdict from the latest scan.

    One row per (document_id, scan_run). The latest open row for each
    document_id surfaces in the UI. Resolved rows stay for audit history.
    """
    __tablename__ = "document_assignment_qc_results"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, nullable=False, index=True)
    current_shipment_id = Column(Integer, nullable=True)
    suspected_shipment_id = Column(Integer, nullable=True)
    confidence_score = Column(Integer, nullable=False)  # 0..100
    severity = Column(String, nullable=True)            # ok / minor / suspicious / strong_mismatch
    status = Column(String, default="open", nullable=False)
    # open / approved_keep / approved_move / approved_detach
    # / dismissed_false_positive / ignored / superseded
    mismatch_reasons_json = Column(JSON, nullable=True)
    matched_signals_json = Column(JSON, nullable=True)
    recommendation = Column(String, nullable=True)
    # keep / review / reassign_suggested / detach_suggested
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(String, nullable=True)
    resolution_action = Column(String, nullable=True)
    resolution_note = Column(Text, nullable=True)


class DocumentAssignmentAction(Base):
    """Audit log of every approved QC action.

    Captures the before/after document↔shipment link so any reassignment
    can be reverted if needed. Created ONLY when the user explicitly
    approves a QC suggestion.
    """
    __tablename__ = "document_assignment_actions"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, nullable=False, index=True)
    old_shipment_id = Column(Integer, nullable=True)
    new_shipment_id = Column(Integer, nullable=True)
    action = Column(String, nullable=False)
    # keep / move / detach / mark_correct / ignore
    reason = Column(Text, nullable=True)
    approved_by = Column(String, nullable=True)
    approved_at = Column(DateTime, default=datetime.utcnow)
    qc_result_id = Column(Integer, nullable=True)
    before_json = Column(JSON, nullable=True)
    after_json = Column(JSON, nullable=True)
