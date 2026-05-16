"""Smart shipment-document checklist.

For each required document type, classify the linked attachments and
return a per-type status:

  missing               - no document of this type exists
  document_exists       - document exists but data not yet extracted
  data_extracted        - extracted value exists on the shipment
                          (e.g. invoice_number populated)
  needs_review          - extracted but flagged
  approved              - user-confirmed value
  email_noise           - only noise found

The result is read-only — never mutates shipment fields.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from ..models import EmailAttachment, EmailUpdate, Shipment
from . import document_classifier_service as classifier


REQUIRED_TYPES = ["invoice", "packing_list", "bl"]


def _all_active_docs_for_shipment(db: Session, shipment: Shipment) -> List[EmailAttachment]:
    """All attachments linked to this shipment OR via its containers,
    excluding archived. (Email-noise rows ARE included — caller filters.)
    """
    container_ids = [c.id for c in (shipment.containers or [])]
    from sqlalchemy import or_
    q = db.query(EmailAttachment).filter(
        EmailAttachment.archived == False,   # noqa: E712
        or_(
            EmailAttachment.linked_shipment_id == shipment.id,
            EmailAttachment.linked_container_id.in_(container_ids) if container_ids else False,  # noqa: E712
        ),
    )
    return q.all()


def _shipment_field_for_type(s: Shipment, doc_type: str) -> Optional[str]:
    """Which shipment field, if populated, indicates the data has been
    extracted/confirmed for this document type?"""
    if doc_type == "invoice":
        return s.invoice_number
    if doc_type == "packing_list":
        # No dedicated PL number on Shipment — the file itself is the proof
        return None
    if doc_type == "bl":
        return (s.house_bill_of_lading_number
                or s.master_bill_of_lading_number
                or s.bol_number)
    return None


def get_status(db: Session, shipment: Shipment) -> Dict[str, Any]:
    """Build the smart checklist."""
    docs = _all_active_docs_for_shipment(db, shipment)

    # Group by classification, ignoring noise
    real_docs = [d for d in docs if not d.is_email_noise]
    noise_docs = [d for d in docs if d.is_email_noise]

    # Resolve overrides: manually_classified_by takes priority
    docs_by_type: Dict[str, List[EmailAttachment]] = {}
    for d in real_docs:
        cls = d.classification or "unknown_needs_review"
        docs_by_type.setdefault(cls, []).append(d)

    # Per-required-type status
    by_type: Dict[str, Dict[str, Any]] = {}
    for req in REQUIRED_TYPES:
        satisfiers = classifier.TYPE_SATISFIERS.get(req, set())
        matching: List[EmailAttachment] = []
        for cls, lst in docs_by_type.items():
            if cls in satisfiers:
                matching.extend(lst)

        field_value = _shipment_field_for_type(shipment, req)

        if matching and field_value:
            status = "data_extracted"
            label = "מספר זוהה ומאושר"
        elif matching:
            status = "document_exists"
            label = "המסמך קיים — ערך לא חולץ עדיין"
        else:
            status = "missing"
            label = "המסמך חסר"

        by_type[req] = {
            "required_type": req,
            "status": status,
            "label_he": label,
            "documents": [
                {"id": d.id, "filename": d.filename,
                 "classification": d.classification,
                 "classification_confidence": d.classification_confidence,
                 "manually_set": bool(d.manually_classified_by)}
                for d in matching
            ],
            "shipment_field_value": field_value,
        }

    # Other classified docs (PO, customs, certificate, product image) — show separately
    other_docs = [
        {"id": d.id, "filename": d.filename,
         "classification": d.classification,
         "classification_confidence": d.classification_confidence}
        for d in real_docs
        if (d.classification or "") not in
            {"commercial_invoice", "packing_list",
             "bill_of_lading", "house_bill_of_lading", "master_bill_of_lading"}
    ]

    return {
        "shipment_id": shipment.id,
        "shp_id": shipment.shp_id,
        "by_type": by_type,
        "summary": {
            "missing":          sum(1 for t in by_type.values() if t["status"] == "missing"),
            "document_exists":  sum(1 for t in by_type.values() if t["status"] == "document_exists"),
            "data_extracted":   sum(1 for t in by_type.values() if t["status"] == "data_extracted"),
        },
        "other_documents": other_docs,
        "noise_filtered_count": len(noise_docs),
        "real_documents_count": len(real_docs),
    }


def recalculate(db: Session, shipment: Shipment) -> Dict[str, Any]:
    """Re-classify every attachment of this shipment + return status.
    Persists classification onto each row. Caller commits."""
    docs = _all_active_docs_for_shipment(db, shipment)
    rescanned = 0
    for d in docs:
        eu = None
        if d.email_update_id:
            eu = db.query(EmailUpdate).filter(
                EmailUpdate.id == d.email_update_id
            ).first()
        # Don't overwrite manual classifications
        if not d.manually_classified_by:
            classifier.classify_and_save(d, eu, persist=True)
            rescanned += 1
    db.commit()
    return {**get_status(db, shipment), "rescanned": rescanned}
