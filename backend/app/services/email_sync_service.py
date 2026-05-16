"""Email sync + classification service.

Two responsibilities:
1. Accept emails (from inject endpoint OR Gmail sync) and persist them as
   `EmailUpdate` rows.
2. Classify them: detect SHP-IDs / containers / booking numbers in
   subject+body+(later)PDF text, decide if it's an update for an existing
   shipment, a new shipment, or irrelevant. Create PendingShipment + alerts
   accordingly.

The "fetch raw" and "classify" steps are intentionally separated so that
`gmail_service.sync_inbox` can pull emails fast (status='fetched') and a
separate processor (`process_fetched_emails`) classifies them later — that
allows attaching PDF/Drive content to the parser before classification.
"""
import hashlib
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session

from ..models import (
    EmailUpdate, Shipment, Container, PendingShipment, PendingContainer,
    EmailAttachment,
)
from . import email_parser_service, event_service, dashboard_service, alert_service, email_apply_service, document_service

log = logging.getLogger("email")


def _make_message_id(sender: str, subject: str, received_at: datetime) -> str:
    base = f"{sender}|{subject}|{received_at.isoformat()}"
    return hashlib.md5(base.encode("utf-8")).hexdigest()


def already_processed(db: Session, message_id: str) -> bool:
    return (
        db.query(EmailUpdate)
        .filter(EmailUpdate.email_message_id == message_id)
        .first()
        is not None
    )


def match_existing_shipment(db: Session, fields) -> tuple[Optional[int], float]:
    """Match detected fields against existing shipments.
    Returns (shipment_id, confidence). Accepts either ExtractedFields or
    a legacy dict with keys shp_id/container_numbers/booking_number/bol_number/...
    """
    if hasattr(fields, "shipment_id"):  # ExtractedFields
        shp_id = fields.shipment_id
        container_numbers = fields.container_numbers or []
        booking = fields.booking_number
        bol = fields.bl_number
        invoice = fields.invoice_number
        po = fields.po_number
    else:  # legacy dict
        shp_id = fields.get("shp_id")
        container_numbers = fields.get("container_numbers") or []
        booking = fields.get("booking_number")
        bol = fields.get("bol_number")
        invoice = fields.get("invoice_number")
        po = fields.get("po_number")

    if shp_id:
        s = db.query(Shipment).filter(Shipment.shp_id == shp_id).first()
        if s:
            return s.id, 0.95
    for cn in container_numbers:
        c = db.query(Container).filter(Container.container_number == cn).first()
        if c:
            return c.shipment_id, 0.9
    if booking:
        s = db.query(Shipment).filter(Shipment.booking_number == booking).first()
        if s:
            return s.id, 0.85
    if bol:
        s = db.query(Shipment).filter(Shipment.bol_number == bol).first()
        if s:
            return s.id, 0.85
    if invoice:
        s = db.query(Shipment).filter(Shipment.invoice_number == invoice).first()
        if s:
            return s.id, 0.7
    if po:
        s = db.query(Shipment).filter(Shipment.po_number == po).first()
        if s:
            return s.id, 0.7
    return None, 0.0


def matched_container_id(db: Session, fields) -> Optional[int]:
    if hasattr(fields, "container_numbers"):
        nums = fields.container_numbers or []
    else:
        nums = fields.get("container_numbers") or []
    for cn in nums:
        c = db.query(Container).filter(Container.container_number == cn).first()
        if c:
            return c.id
    return None


def process_email(
    db: Session,
    *,
    sender: str,
    subject: str,
    body: str,
    received_at: Optional[datetime] = None,
    attachment_names: Optional[List[str]] = None,
    message_id: Optional[str] = None,
    thread_id: Optional[str] = None,
) -> EmailUpdate:
    received_at = received_at or datetime.utcnow()
    message_id = message_id or _make_message_id(sender, subject, received_at)

    existing = (
        db.query(EmailUpdate)
        .filter(EmailUpdate.email_message_id == message_id)
        .first()
    )
    if existing:
        return existing

    eu = EmailUpdate(
        email_message_id=message_id,
        email_thread_id=thread_id,
        sender=sender,
        subject=subject,
        received_at=received_at,
        body_excerpt=body[:500],
        full_body_text=body,
        attachment_names=attachment_names or [],
        status="fetched",  # raw — classify_email() upgrades this
    )
    db.add(eu)
    db.flush()

    classify_email(db, eu)

    event_service.log_event(
        db,
        entity_type="email_update",
        entity_id=eu.id,
        action_type="email_received",
        new_value=subject,
        changed_by="system",
        source="email_import",
        note=f"sender={sender}, type={eu.detection_type}",
    )
    db.commit()
    db.refresh(eu)
    return eu


# =====================================================================
# Classification — extracted so it can be re-run on existing EUs
# =====================================================================

def classify_email(
    db: Session,
    eu: EmailUpdate,
    *,
    extra_text: str = "",
) -> EmailUpdate:
    """Step 2 + 3 of the pipeline.

    1. Run parser on (subject + body + optional extra_text)
    2. Save detection_type + confidence + extracted fields → status='parsed'
    3. Dispatch by detection_type:
       - 'update': create alert (email_update_awaiting_approval), keep eu pending
       - 'delay':  create alert (delay_detected), keep eu pending
       - 'new_shipment': create PendingShipment + alert
       - 'unknown': mark ignored

    Caller is responsible for db.commit(). The eu is assumed to already be
    flushed (has an id).

    `extra_text` is the seam for PDF/Drive content — currently unused by
    Gmail sync but reserved for the next phase.
    """
    # ---- (1) Parse ----
    parsed = email_parser_service.parse_email(eu, extra_text=extra_text)
    matched_id, match_conf = match_existing_shipment(db, parsed.extracted_fields)
    parsed = email_parser_service.reclassify_with_match(parsed, has_match=bool(matched_id))
    if matched_id:
        # If we matched, prefer the match-based confidence
        parsed.confidence_score = max(parsed.confidence_score, match_conf)

    # ---- (2) Save parsed result ----
    eu.detection_type = parsed.detection_type
    eu.confidence_score = parsed.confidence_score
    eu.detected_fields_json = parsed.to_jsonable()
    eu.detected_shipment_id = matched_id
    eu.detected_container_id = matched_container_id(db, parsed.extracted_fields) if matched_id else None
    eu.status = "parsed"
    db.flush()

    log.info(
        "EU#%s parsed → type=%s conf=%.2f shp=%s summary=%r",
        eu.id, parsed.detection_type, parsed.confidence_score,
        matched_id, parsed.summary,
    )

    # ---- (2.5) Link any orphan EmailAttachments to the matched shipment ----
    if matched_id:
        orphans = db.query(EmailAttachment).filter(
            EmailAttachment.email_update_id == eu.id,
            EmailAttachment.linked_shipment_id.is_(None),
        ).all()
        for att in orphans:
            att.linked_shipment_id = matched_id
            if eu.detected_container_id:
                att.linked_container_id = eu.detected_container_id
        if orphans:
            db.flush()
            log.info("EU#%s: linked %d orphan attachments to shipment#%s",
                     eu.id, len(orphans), matched_id)

    # ---- (3) Dispatch by detection_type ----
    if parsed.detection_type == "new_shipment":
        # Don't auto-create shipments — always require user approval
        _create_pending_shipment(db, eu, parsed)
        eu.needs_review = True
    elif parsed.detection_type in ("update", "delay") and matched_id:
        # AUTO-APPLY policy: write safe fields to the shipment immediately.
        # Risky changes are flagged for review (alert created inside the apply
        # service). Delay always creates an alert.
        shipment = db.query(Shipment).filter(Shipment.id == matched_id).first()
        if shipment:
            apply_result = email_apply_service.apply_email_to_shipment(
                db, eu, shipment, actor="system",
            )
            if apply_result.needs_review:
                eu.status = "needs_review"
            elif apply_result.applied or apply_result.added_containers:
                eu.status = "approved"   # auto-applied, nothing to review
                eu.approved_by = "system"
                eu.approved_at = datetime.utcnow()
            else:
                # Nothing changed (all noop)
                eu.status = "ignored"
    else:  # unknown
        eu.status = "ignored"
        db.flush()

    return eu


def _create_pending_shipment(db, eu: EmailUpdate, parsed) -> None:
    f = parsed.extracted_fields
    # Idempotency — don't double-create on re-parse
    existing = (
        db.query(PendingShipment)
        .filter(PendingShipment.source_email_update_id == eu.id)
        .first()
    )
    if existing:
        return
    ps = PendingShipment(
        source_email_update_id=eu.id,
        detected_supplier=f.supplier,
        detected_goods_description=eu.subject,
        detected_etd=f.etd,
        detected_eta_israel=f.eta_israel,
        detected_eta_port=f.eta_port,
        detected_eta_warehouse=f.eta_warehouse,
        detected_booking_number=f.booking_number,
        detected_bol_number=f.bl_number,
        detected_invoice_number=f.invoice_number,
        detected_po_number=f.po_number,
        detected_notes=(eu.body_excerpt or "")[:500],
        detected_fields_json=f.to_jsonable(),
        confidence_score=parsed.confidence_score,
        status="pending",
    )
    db.add(ps)
    db.flush()
    for cn in f.container_numbers or []:
        db.add(PendingContainer(
            pending_shipment_id=ps.id,
            detected_container_number=cn,
        ))
    db.flush()
    alert_service.create_alert(
        db,
        alert_type="pending_shipment_awaiting_approval",
        title="זוהה משלוח חדש ממייל",
        description=eu.subject,
        severity="high",
        pending_shipment_id=ps.id,
        email_update_id=eu.id,
    )


def _alert_update_pending(db, eu: EmailUpdate, shipment_id: int) -> None:
    alert_service.create_alert(
        db,
        alert_type="email_update_awaiting_approval",
        title="עדכון ממייל ממתין לאישור",
        description=eu.subject,
        severity="medium",
        email_update_id=eu.id,
        shipment_id=shipment_id,
    )


def _alert_delay(db, eu: EmailUpdate, shipment_id: Optional[int], summary: str) -> None:
    s = db.query(Shipment).filter(Shipment.id == shipment_id).first() if shipment_id else None
    title = f"זוהה עיכוב במייל" + (f" — {s.shp_id}" if s else "")
    alert_service.create_alert(
        db,
        alert_type="delay_detected_in_email",
        title=title,
        description=(eu.subject or "") + " | " + summary,
        severity="high",
        shipment_id=shipment_id,
        email_update_id=eu.id,
    )


def process_fetched_emails(db: Session, *, limit: int = 500) -> Dict[str, Any]:
    """Run classify_email() on every EmailUpdate that's still status='fetched'.

    This is the post-Gmail-sync step that turns raw emails into
    classified updates / pending shipments / alerts.
    """
    log.info("process_fetched_emails: start")
    rows = (
        db.query(EmailUpdate)
        .filter(EmailUpdate.status == "fetched")
        .order_by(EmailUpdate.id.asc())
        .limit(limit)
        .all()
    )
    log.info("process_fetched_emails: %d rows to process", len(rows))

    counts: Dict[str, int] = {
        "processed": 0,
        "update": 0,
        "delay": 0,
        "new_shipment": 0,
        "unknown": 0,
        "errors": 0,
    }
    error_details: List[Dict[str, Any]] = []

    for eu in rows:
        try:
            classify_email(db, eu)
            db.commit()
            counts["processed"] += 1
            counts[eu.detection_type] = counts.get(eu.detection_type, 0) + 1
            event_service.log_event(
                db,
                entity_type="email_update",
                entity_id=eu.id,
                action_type="parsed",
                new_value=eu.detection_type,
                changed_by="system",
                source="email_import",
                note=f"conf={eu.confidence_score}, shp={eu.detected_shipment_id}",
            )
            db.commit()
        except Exception as e:
            db.rollback()
            log.exception("process_fetched_emails: failed on EU#%s", eu.id)
            counts["errors"] += 1
            error_details.append({"id": eu.id, "error": str(e)})

    log.info("process_fetched_emails done: %s", counts)
    return {**counts, "errors_detail": error_details}


def sync_now(db: Session) -> Dict[str, Any]:
    """Stub. Real implementation would fetch from Gmail/Outlook here.
    For MVP we just record sync time."""
    dashboard_service.set_last_email_sync()
    return {
        "synced_at": datetime.utcnow().isoformat(),
        "message": "סנכרון בוצע. במצב MVP, מיילים נכנסים דרך POST /email/inject.",
    }


def _extract_fields_from_eu(eu: EmailUpdate) -> Dict[str, Any]:
    """Read the structured ExtractedFields out of an EU's detected_fields_json
    regardless of whether it's the new shape ({extracted_fields: {...}}) or
    a legacy flat shape from the old parser."""
    raw = eu.detected_fields_json or {}
    if isinstance(raw, dict) and "extracted_fields" in raw:
        return raw.get("extracted_fields") or {}
    return raw  # legacy flat dict


def approve_update(db: Session, email_update_id: int, approved_by: str = "admin") -> EmailUpdate:
    from . import shipment_service
    from ..schemas.shipment import ShipmentUpdate
    from fastapi import HTTPException

    eu = db.query(EmailUpdate).filter(EmailUpdate.id == email_update_id).first()
    if not eu:
        raise HTTPException(status_code=404, detail="Email update not found")
    if not eu.detected_shipment_id:
        raise HTTPException(status_code=400, detail="לא משויך למשלוח")

    f = _extract_fields_from_eu(eu)
    update_payload: Dict[str, Any] = {}

    # Field name mapping: new ExtractedFields → Shipment columns
    if f.get("eta_israel"):
        update_payload["eta_israel"] = f["eta_israel"]
    if f.get("eta_warehouse"):
        update_payload["eta_warehouse"] = f["eta_warehouse"]
    if f.get("eta_port"):
        update_payload["eta_port"] = f["eta_port"]
    if f.get("etd"):
        update_payload["etd"] = f["etd"]
    if f.get("booking_number"):
        update_payload["booking_number"] = f["booking_number"]
    # Both shapes — bl_number (new) and bol_number (legacy)
    if f.get("bl_number") or f.get("bol_number"):
        update_payload["bol_number"] = f.get("bl_number") or f.get("bol_number")
    if f.get("invoice_number"):
        update_payload["invoice_number"] = f["invoice_number"]
    if f.get("po_number"):
        update_payload["po_number"] = f["po_number"]
    # Delay can be flagged either way
    if f.get("delay_detected") or f.get("delay_status"):
        update_payload["delay_status"] = True
        update_payload["delay_reason"] = "זוהה עיכוב במייל — דורש פירוט"

    if update_payload:
        # Convert ISO date strings back to date objects for the schema
        from datetime import date as _date
        for k in ("eta_israel", "eta_warehouse", "eta_port", "etd"):
            if k in update_payload and isinstance(update_payload[k], str):
                try:
                    update_payload[k] = _date.fromisoformat(update_payload[k])
                except Exception:
                    update_payload.pop(k, None)
        # Build update model — but skip delay if no reason
        if update_payload.get("delay_status") and not update_payload.get("delay_reason"):
            update_payload.pop("delay_status", None)
        try:
            payload = ShipmentUpdate(**update_payload)
            shipment_service.update_shipment(
                db, eu.detected_shipment_id, payload,
                updated_by=approved_by, source="email",
            )
        except Exception as e:
            # Surface as needs_review with the original data preserved
            eu.status = "needs_review"
            db.commit()
            raise

    eu.status = "approved"
    eu.approved_by = approved_by
    eu.approved_at = datetime.utcnow()

    event_service.log_event(
        db,
        entity_type="email_update",
        entity_id=eu.id,
        action_type="approve",
        changed_by=approved_by,
        source="manual",
        note="עדכון ממייל אושר",
    )
    db.commit()
    db.refresh(eu)
    return eu


def reject_update(db: Session, email_update_id: int, rejected_by: str = "admin") -> EmailUpdate:
    eu = db.query(EmailUpdate).filter(EmailUpdate.id == email_update_id).first()
    if not eu:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Email update not found")
    eu.status = "rejected"
    eu.rejected_by = rejected_by
    eu.rejected_at = datetime.utcnow()
    event_service.log_event(
        db,
        entity_type="email_update",
        entity_id=eu.id,
        action_type="reject",
        changed_by=rejected_by,
        source="manual",
    )
    db.commit()
    db.refresh(eu)
    return eu


def assign_update(db: Session, email_update_id: int, shipment_id: int, approved_by: str = "admin") -> EmailUpdate:
    eu = db.query(EmailUpdate).filter(EmailUpdate.id == email_update_id).first()
    if not eu:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Email update not found")
    s = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not s:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Shipment not found")
    eu.detected_shipment_id = shipment_id
    eu.detection_type = "update_existing"
    eu.status = "pending"
    event_service.log_event(
        db,
        entity_type="email_update",
        entity_id=eu.id,
        action_type="assign",
        new_value=s.shp_id,
        changed_by=approved_by,
        source="manual",
    )
    db.commit()
    db.refresh(eu)
    return eu
