"""Documents — list, view, link, reassign.

Underlying model: EmailAttachment.
"""
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import EmailAttachment, Shipment, Container, EmailUpdate
from ..services import (
    document_service, event_service, excel_preview_service, document_qc_service,
    document_classifier_service, document_status_service,
)
from ..services.auth_service import require_permission
from ..models import User, Shipment

router = APIRouter(prefix="/documents", tags=["documents"])
log = logging.getLogger("documents")


def _enrich(att: EmailAttachment, db: Session) -> dict:
    d = {col.name: getattr(att, col.name) for col in att.__table__.columns}
    if att.email_update_id:
        eu = db.query(EmailUpdate).filter(EmailUpdate.id == att.email_update_id).first()
        if eu:
            d["source_email_sender"] = eu.sender
            d["source_email_subject"] = eu.subject
            d["received_at"] = eu.received_at.isoformat() if eu.received_at else None
    if att.linked_shipment_id:
        s = db.query(Shipment).filter(Shipment.id == att.linked_shipment_id).first()
        if s:
            d["shp_id"] = s.shp_id
            d["supplier"] = s.supplier
    if att.linked_container_id:
        c = db.query(Container).filter(Container.id == att.linked_container_id).first()
        if c:
            d["container_number"] = c.container_number
    return d


@router.get("")
def list_documents(
    shipment_id: Optional[int] = None,
    container_id: Optional[int] = None,
    unassigned: Optional[bool] = None,
    document_type: Optional[str] = None,
    include_archived: bool = False,
    db: Session = Depends(get_db),
):
    q = db.query(EmailAttachment)
    # Hide archived rows by default — pass include_archived=true to see them
    if not include_archived:
        q = q.filter(EmailAttachment.archived == False)  # noqa: E712
    if shipment_id is not None:
        q = q.filter(EmailAttachment.linked_shipment_id == shipment_id)
    if container_id is not None:
        q = q.filter(EmailAttachment.linked_container_id == container_id)
    if unassigned:
        q = q.filter(EmailAttachment.linked_shipment_id.is_(None))
    if document_type:
        q = q.filter(EmailAttachment.document_type == document_type)
    rows = q.order_by(EmailAttachment.id.desc()).limit(500).all()
    return [_enrich(a, db) for a in rows]


@router.get("/filtered-noise")
def list_filtered_noise_alias(
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("document.read")),
):
    """List of email_noise attachments. Declared BEFORE /{doc_id} so the
    static path wins over the parametric one."""
    rows = (
        db.query(EmailAttachment)
        .filter(
            EmailAttachment.archived == False,   # noqa: E712
            EmailAttachment.is_email_noise == True,   # noqa: E712
        )
        .order_by(EmailAttachment.id.desc())
        .limit(500)
        .all()
    )
    return [_enrich(a, db) for a in rows]


@router.post("/classify-all")
def classify_all_alias(
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("document.assign")),
):
    """Bulk re-classify every active attachment. Skips manually-classified rows."""
    rows = (
        db.query(EmailAttachment)
        .filter(EmailAttachment.archived == False)   # noqa: E712
        .all()
    )
    classified = 0
    for att in rows:
        if att.manually_classified_by:
            continue
        eu = None
        if att.email_update_id:
            eu = db.query(EmailUpdate).filter(EmailUpdate.id == att.email_update_id).first()
        document_classifier_service.classify_and_save(att, eu, persist=True)
        classified += 1
    db.commit()
    return {"total": len(rows), "classified": classified,
            "skipped_manual": len(rows) - classified}


@router.get("/{doc_id}")
def get_document(doc_id: int, db: Session = Depends(get_db)):
    att = db.query(EmailAttachment).filter(EmailAttachment.id == doc_id).first()
    if not att:
        raise HTTPException(status_code=404, detail="Document not found")
    return _enrich(att, db)


def _resolve_file(att: EmailAttachment) -> Path:
    """Locate the on-disk file for an attachment + sanity-check it.
    Raises HTTPException with clear codes:
      404 if no file_path or missing on disk
      422 if 0-byte
    """
    if not att or not att.file_path:
        raise HTTPException(status_code=404, detail="Document not found")
    fpath = document_service.DOCS_DIR / Path(att.file_path).name
    if not fpath.exists():
        raise HTTPException(status_code=404, detail="File missing on disk")
    if fpath.stat().st_size == 0:
        raise HTTPException(status_code=422, detail="File is empty or corrupted")
    return fpath


def _safe_ascii_filename(name: str) -> str:
    """Strip non-ASCII and dangerous characters for Content-Disposition fallback.
    The full UTF-8 filename is sent via filename* (RFC 5987)."""
    if not name:
        return "document"
    # Replace NBSP and other unicode whitespace with regular space
    cleaned = name.replace("\xa0", " ").strip()
    # Build ASCII-only fallback (Latin-1 chars only, replace others)
    ascii_only = "".join(c if 0x20 < ord(c) < 0x7F and c not in '"\\' else "_" for c in cleaned)
    # Collapse repeated underscores/spaces
    import re
    ascii_only = re.sub(r"[_\s]+", "_", ascii_only).strip("_")
    return ascii_only[:120] or "document"


def _content_disposition(filename: str, *, disposition: str) -> str:
    """RFC 6266-compliant Content-Disposition header with both filename and filename*."""
    from urllib.parse import quote
    fallback = _safe_ascii_filename(filename or "document")
    cleaned = (filename or "document").replace("\xa0", " ").strip()
    encoded = quote(cleaned, safe="")
    return f"{disposition}; filename=\"{fallback}\"; filename*=UTF-8''{encoded}"


@router.get("/{doc_id}/download")
def download_document(doc_id: int, db: Session = Depends(get_db)):
    att = db.query(EmailAttachment).filter(EmailAttachment.id == doc_id).first()
    fpath = _resolve_file(att)
    return FileResponse(
        str(fpath),
        media_type=att.file_type or "application/octet-stream",
        headers={
            "Content-Disposition": _content_disposition(
                att.filename or fpath.name, disposition="attachment"
            ),
            # Explicit length helps Windows / IE-style downloaders
            "Content-Length": str(fpath.stat().st_size),
        },
    )


@router.get("/{doc_id}/preview")
def preview_document(doc_id: int, db: Session = Depends(get_db)):
    """Inline preview — sends Content-Disposition: inline so the browser
    renders PDFs/images instead of downloading."""
    att = db.query(EmailAttachment).filter(EmailAttachment.id == doc_id).first()
    fpath = _resolve_file(att)
    return FileResponse(
        str(fpath),
        media_type=att.file_type or "application/octet-stream",
        headers={
            "Content-Disposition": _content_disposition(
                att.filename or fpath.name, disposition="inline"
            ),
        },
    )


@router.get("/{doc_id}/excel-preview")
def excel_preview(doc_id: int, db: Session = Depends(get_db)):
    """Excel → JSON sheets for inline preview. Caps at 200 rows × 30 cols per sheet."""
    att = db.query(EmailAttachment).filter(EmailAttachment.id == doc_id).first()
    fpath = _resolve_file(att)
    result = excel_preview_service.preview(fpath)
    return {
        "id": att.id,
        "filename": att.filename,
        "size": fpath.stat().st_size,
        **result,
    }


@router.post("/{doc_id}/redownload")
def redownload_document(doc_id: int, db: Session = Depends(get_db)):
    """Re-download a single attachment from Gmail (useful if the on-disk file
    got corrupted or was never saved). Skips Drive links and manual uploads."""
    att = db.query(EmailAttachment).filter(EmailAttachment.id == doc_id).first()
    if not att:
        raise HTTPException(status_code=404, detail="Document not found")
    if not att.gmail_attachment_id:
        raise HTTPException(
            status_code=400,
            detail="ניתן להוריד מחדש רק מסמכים שמקורם ב-Gmail attachment",
        )
    if not att.email_update_id:
        raise HTTPException(status_code=400, detail="No source email")

    from ..services import gmail_service
    eu = db.query(EmailUpdate).filter(EmailUpdate.id == att.email_update_id).first()
    if not eu or not eu.email_message_id:
        raise HTTPException(status_code=400, detail="Source email not found")

    creds = gmail_service._load_credentials()
    if not creds or not creds.valid:
        raise HTTPException(status_code=401, detail="Gmail not connected")
    from googleapiclient.discovery import build
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)

    fpath = gmail_service.download_attachment_to_disk(
        service,
        gmail_message_id=eu.email_message_id,
        gmail_attachment_id=att.gmail_attachment_id,
        filename=att.filename or "attachment",
        mime_type=att.file_type or "",
        eu_id=eu.id,
    )
    if not fpath:
        raise HTTPException(status_code=500, detail="Re-download failed")
    att.file_path = f"documents/{fpath.name}"
    att.file_size = fpath.stat().st_size
    db.commit()
    return {
        "id": att.id,
        "filename": att.filename,
        "file_path": att.file_path,
        "size": att.file_size,
        "ok": True,
    }


@router.post("/redownload-invalid")
def redownload_invalid(db: Session = Depends(get_db)):
    """Bulk: re-download every Gmail-sourced attachment whose file is missing or empty."""
    from ..services import gmail_service
    creds = gmail_service._load_credentials()
    if not creds or not creds.valid:
        raise HTTPException(status_code=401, detail="Gmail not connected")
    from googleapiclient.discovery import build
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)

    rows = db.query(EmailAttachment).filter(
        EmailAttachment.gmail_attachment_id.isnot(None),
        EmailAttachment.email_update_id.isnot(None),
    ).all()
    fixed = 0
    skipped_ok = 0
    failed: List[dict] = []
    for att in rows:
        if att.file_path:
            fpath = document_service.DOCS_DIR / Path(att.file_path).name
            if fpath.exists() and fpath.stat().st_size > 0:
                skipped_ok += 1
                continue
        eu = db.query(EmailUpdate).filter(EmailUpdate.id == att.email_update_id).first()
        if not eu or not eu.email_message_id:
            failed.append({"id": att.id, "reason": "no source email"})
            continue
        try:
            new_fpath = gmail_service.download_attachment_to_disk(
                service,
                gmail_message_id=eu.email_message_id,
                gmail_attachment_id=att.gmail_attachment_id,
                filename=att.filename or "attachment",
                mime_type=att.file_type or "",
                eu_id=eu.id,
            )
            if new_fpath:
                att.file_path = f"documents/{new_fpath.name}"
                att.file_size = new_fpath.stat().st_size
                fixed += 1
            else:
                failed.append({"id": att.id, "reason": "download returned None"})
        except Exception as e:
            failed.append({"id": att.id, "reason": str(e)})
    db.commit()
    return {"fixed": fixed, "skipped_ok": skipped_ok, "failed": failed}


@router.get("/{doc_id}/file-status")
def file_status(doc_id: int, db: Session = Depends(get_db)):
    """Lightweight validity check — used by UI to enable/disable buttons.
    Status: valid / missing / empty / drive_link / no_file."""
    att = db.query(EmailAttachment).filter(EmailAttachment.id == doc_id).first()
    if not att:
        raise HTTPException(status_code=404, detail="Document not found")
    if att.source_url and not att.file_path:
        return {"id": att.id, "status": "drive_link", "size": None, "signature": None}
    if not att.file_path:
        return {"id": att.id, "status": "no_file", "size": None, "signature": None}
    fpath = document_service.DOCS_DIR / Path(att.file_path).name
    if not fpath.exists():
        return {"id": att.id, "status": "missing", "size": None, "signature": None}
    size = fpath.stat().st_size
    if size == 0:
        return {"id": att.id, "status": "empty", "size": 0, "signature": None}
    with open(fpath, "rb") as f:
        head = f.read(8)
    sig = (
        "pdf" if head[:4] == b"%PDF" else
        "ooxml" if head[:4] == b"PK\x03\x04" else
        "ole" if head[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" else
        "image_jpeg" if head[:3] == b"\xff\xd8\xff" else
        "image_png" if head[:4] == b"\x89PNG" else
        "image_gif" if head[:4] == b"GIF8" else
        "unknown"
    )
    return {"id": att.id, "status": "valid", "size": size, "signature": sig}


@router.put("/{doc_id}/assign")
def assign_document(
    doc_id: int,
    shipment_id: Optional[int] = None,
    container_id: Optional[int] = None,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("document.assign")),
):
    att = db.query(EmailAttachment).filter(EmailAttachment.id == doc_id).first()
    if not att:
        raise HTTPException(status_code=404, detail="Document not found")
    if shipment_id is not None:
        s = db.query(Shipment).filter(Shipment.id == shipment_id).first()
        if not s:
            raise HTTPException(status_code=404, detail="Shipment not found")
        att.linked_shipment_id = shipment_id
    if container_id is not None:
        c = db.query(Container).filter(Container.id == container_id).first()
        if not c:
            raise HTTPException(status_code=404, detail="Container not found")
        att.linked_container_id = container_id
        if shipment_id is None:  # auto-fill shipment from container
            att.linked_shipment_id = c.shipment_id
    event_service.log_event(
        db, entity_type="email_attachment", entity_id=att.id,
        action_type="assign_document",
        new_value=f"shp={shipment_id} cont={container_id}",
        changed_by=actor.full_name or actor.username, source="manual",
    )
    db.commit()
    db.refresh(att)
    # Re-scan this single doc so QC immediately reflects the new link
    try:
        document_qc_service.run_scan(db, only_doc_ids=[att.id])
    except Exception as e:
        log.warning("QC re-scan after assign failed (non-fatal): %s", e)
    return _enrich(att, db)


@router.put("/{doc_id}/document-type")
def change_document_type(
    doc_id: int,
    document_type: str,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("document.assign")),
):
    att = db.query(EmailAttachment).filter(EmailAttachment.id == doc_id).first()
    if not att:
        raise HTTPException(status_code=404, detail="Document not found")
    old = att.document_type
    att.document_type = document_type
    event_service.log_event(
        db, entity_type="email_attachment", entity_id=att.id,
        action_type="change_document_type",
        old_value=old, new_value=document_type,
        changed_by=actor.full_name or actor.username, source="manual",
    )
    db.commit()
    db.refresh(att)
    return _enrich(att, db)


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    shipment_id: Optional[int] = Form(None),
    container_id: Optional[int] = Form(None),
    document_type: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("document.upload")),
):
    """Manual upload — for cases where a document arrived outside the email flow.

    Note: EmailAttachment.email_update_id is NOT NULL in the schema, so we
    create (or reuse) a 'manual_upload' placeholder EmailUpdate as a parent."""
    from datetime import datetime
    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="קובץ ריק")
    safe_name = (file.filename or "doc").replace("/", "_").replace("\\", "_")
    fname = f"manual_{safe_name}"
    fpath = document_service.DOCS_DIR / fname
    # Avoid clobbering: append uuid suffix if exists
    if fpath.exists():
        import uuid as _uuid
        stem, suf = Path(fname).stem, Path(fname).suffix
        fname = f"{stem}_{_uuid.uuid4().hex[:6]}{suf}"
        fpath = document_service.DOCS_DIR / fname
    fpath.write_bytes(contents)
    dt = document_type or document_service.guess_document_type(filename=safe_name)

    # Create a per-upload placeholder EmailUpdate so EmailAttachment.email_update_id
    # has a valid parent (NOT NULL constraint).
    placeholder = EmailUpdate(
        sender="manual_upload",
        subject=f"Manual upload: {safe_name}",
        received_at=datetime.utcnow(),
        body_excerpt=f"Uploaded file: {safe_name}",
        attachment_names=[safe_name],
        status="manual_upload",
    )
    db.add(placeholder)
    db.flush()

    att = EmailAttachment(
        email_update_id=placeholder.id,
        filename=safe_name,
        file_type=file.content_type,
        file_size=len(contents),
        file_path=f"documents/{fname}",
        document_type=dt,
        linked_shipment_id=shipment_id,
        linked_container_id=container_id,
    )
    db.add(att)
    db.flush()
    event_service.log_event(
        db, entity_type="email_attachment", entity_id=att.id,
        action_type="manual_upload", new_value=safe_name,
        changed_by=actor.full_name or actor.username, source="manual",
    )
    db.commit()
    # Re-scan only this newly uploaded doc — fast, never blocks the response
    try:
        document_qc_service.run_scan(db, only_doc_ids=[att.id])
    except Exception as e:
        log.warning("QC scan after upload failed (non-fatal): %s", e)
    return _enrich(att, db)


@router.get("/required-status/{shipment_id}")
def required_status(shipment_id: int, db: Session = Depends(get_db)):
    """Smart document checklist — see document_status_service.get_status().

    Output keys:
      by_type: invoice/packing_list/bl → {status, label_he, documents[]}
      summary: counts of each status
      other_documents: PO/customs/certificate/product_image
      noise_filtered_count: how many email_noise docs were excluded

    Backward-compat block — also returns the legacy {present, missing,
    is_complete, count} so the existing UI code keeps working.
    """
    s = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Shipment not found")

    smart = document_status_service.get_status(db, s)

    # Legacy compat — derive {present, missing, is_complete, count}
    present_set = {req for req, info in smart["by_type"].items()
                   if info["status"] in ("document_exists", "data_extracted")}
    if "bl" in present_set:
        present_set.add("bol")
        present_set.add("booking_confirmation")
    missing_set = [req for req, info in smart["by_type"].items()
                   if info["status"] == "missing"]
    return {
        # Legacy
        "present": sorted(present_set),
        "missing": missing_set,
        "is_complete": not missing_set,
        "count": smart["real_documents_count"],
        # Smart
        **smart,
    }


@router.post("/{doc_id}/classify")
def classify_document(
    doc_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("document.assign")),
):
    """Re-run the classifier on one document. Persists the result + reason."""
    att = db.query(EmailAttachment).filter(EmailAttachment.id == doc_id).first()
    if not att:
        raise HTTPException(status_code=404, detail="Document not found")
    eu = None
    if att.email_update_id:
        eu = db.query(EmailUpdate).filter(EmailUpdate.id == att.email_update_id).first()
    result = document_classifier_service.classify_and_save(att, eu, persist=True)
    db.commit()
    db.refresh(att)
    return {
        "id": att.id, "filename": att.filename,
        "classification": att.classification,
        "classification_confidence": att.classification_confidence,
        "classification_reason": att.classification_reason,
        "is_email_noise": att.is_email_noise,
        "manually_classified_by": att.manually_classified_by,
    }


class SetTypeRequest(BaseModel):
    classification: str   # one of the documented vocabulary
    reason: Optional[str] = None


@router.post("/{doc_id}/set-type")
def set_document_type(
    doc_id: int,
    payload: SetTypeRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("document.assign")),
):
    """Manually pick a classification — overrides the auto-classifier."""
    valid = {
        "shipment_document", "commercial_invoice", "packing_list",
        "bill_of_lading", "house_bill_of_lading", "master_bill_of_lading",
        "purchase_order", "customs_document", "delivery_note", "certificate",
        "product_image", "email_noise", "unknown_needs_review",
    }
    if payload.classification not in valid:
        raise HTTPException(status_code=400,
                            detail=f"classification לא חוקי: {payload.classification}")
    att = db.query(EmailAttachment).filter(EmailAttachment.id == doc_id).first()
    if not att:
        raise HTTPException(status_code=404, detail="Document not found")

    actor_name = actor.full_name or actor.username
    old = att.classification
    att.classification = payload.classification
    att.classification_confidence = 1.0
    att.classification_reason = (payload.reason
                                 or f"manually set to {payload.classification}")
    att.classified_at = datetime.utcnow()
    att.is_email_noise = (payload.classification == "email_noise")
    att.manually_classified_by = actor_name
    att.manually_classified_at = datetime.utcnow()

    # Sync the legacy document_type field so existing logic keeps working
    legacy_map = {
        "commercial_invoice": "invoice",
        "packing_list": "packing_list",
        "bill_of_lading": "bl",
        "house_bill_of_lading": "bl",
        "master_bill_of_lading": "bl",
        "purchase_order": "other",   # no legacy slot
        "customs_document": "customs",
        "certificate": "other",
        "delivery_note": "other",
        "product_image": "other",
        "email_noise": "other",
        "shipment_document": "other",
        "unknown_needs_review": "other",
    }
    att.document_type = legacy_map.get(payload.classification, "other")

    event_service.log_event(
        db, entity_type="email_attachment", entity_id=att.id,
        action_type="set_classification",
        old_value=old, new_value=payload.classification,
        changed_by=actor_name, source="manual",
        note=payload.reason,
    )
    db.commit()
    return {
        "id": att.id, "classification": att.classification,
        "is_email_noise": att.is_email_noise,
        "manually_classified_by": att.manually_classified_by,
    }


@router.post("/{doc_id}/mark-noise")
def mark_as_noise(
    doc_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("document.assign")),
):
    """Shortcut to flag a document as email_noise — hides from listings."""
    return set_document_type(
        doc_id, SetTypeRequest(classification="email_noise",
                                reason="hidden as email noise"),
        db=db, actor=actor,
    )


@router.post("/{doc_id}/restore-as-document")
def restore_as_document(
    doc_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("document.assign")),
):
    """Un-flag a noise-marked document — returns it to the auto-classifier
    suggestion so it appears under שimchments documents again."""
    att = db.query(EmailAttachment).filter(EmailAttachment.id == doc_id).first()
    if not att:
        raise HTTPException(status_code=404, detail="Document not found")
    att.is_email_noise = False
    # Clear manual classification so the next /classify call re-runs auto rules
    att.manually_classified_by = None
    att.manually_classified_at = None
    actor_name = actor.full_name or actor.username
    eu = None
    if att.email_update_id:
        eu = db.query(EmailUpdate).filter(EmailUpdate.id == att.email_update_id).first()
    document_classifier_service.classify_and_save(att, eu, persist=True)
    event_service.log_event(
        db, entity_type="email_attachment", entity_id=att.id,
        action_type="restore_as_document",
        new_value=att.classification,
        changed_by=actor_name, source="manual",
    )
    db.commit()
    return {
        "id": att.id, "classification": att.classification,
        "is_email_noise": att.is_email_noise,
    }


# (filtered-noise and classify-all are declared earlier — before /{doc_id} —
#  so static paths win over the parametric path.)


@router.post("/auto-link")
def auto_link_unassigned(
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("document.assign")),
):
    """Re-run the linking heuristic on every unassigned EmailAttachment.
    Uses filename clues + email parsed fields. Safe to run multiple times —
    only affects rows that aren't already linked."""
    unassigned = db.query(EmailAttachment).filter(
        EmailAttachment.linked_shipment_id.is_(None)
    ).all()
    linked_now = 0
    skipped = 0
    for att in unassigned:
        eu = None
        if att.email_update_id:
            eu = db.query(EmailUpdate).filter(EmailUpdate.id == att.email_update_id).first()
        ship_id, cont_id = document_service.attempt_link_to_shipment(
            db,
            parsed_fields=eu.detected_fields_json if eu else None,
            sender=eu.sender if eu else None,
            filename=att.filename,
        )
        if not ship_id and eu and eu.detected_shipment_id:
            ship_id = eu.detected_shipment_id
        if not cont_id and eu and eu.detected_container_id:
            cont_id = eu.detected_container_id

        if ship_id:
            att.linked_shipment_id = ship_id
            if cont_id:
                att.linked_container_id = cont_id
            linked_now += 1
        else:
            skipped += 1
    db.commit()
    return {
        "scanned": len(unassigned),
        "linked": linked_now,
        "still_unassigned": skipped,
    }


def _possible_matches_for(db: Session, att: EmailAttachment, eu: Optional[EmailUpdate]) -> List[dict]:
    """Suggest candidate shipments for an unassigned document.
    Returns up to 5 candidates with a confidence score."""
    candidates: Dict[int, float] = {}

    # 1. Filename-based hints (strongest)
    fn_clues = document_service._scan_filename_for_identifiers(att.filename or "")
    if (shp := fn_clues.get("shipment_id")):
        s = db.query(Shipment).filter(Shipment.shp_id == shp).first()
        if s:
            candidates[s.id] = max(candidates.get(s.id, 0), 0.95)
    for cn in fn_clues.get("container_numbers") or []:
        c = db.query(Container).filter(Container.container_number == cn).first()
        if c:
            candidates[c.shipment_id] = max(candidates.get(c.shipment_id, 0), 0.9)
    if (cart := fn_clues.get("cartons")):
        for c in db.query(Container).filter(Container.boxes_total == cart).all():
            candidates[c.shipment_id] = max(candidates.get(c.shipment_id, 0), 0.7)

    # 2. Sender-supplier match (weak)
    if eu and eu.sender:
        sender_low = eu.sender.lower()
        for s in db.query(Shipment).filter(Shipment.archived == False).all():  # noqa: E712
            if s.supplier and any(part in sender_low for part in s.supplier.lower().split() if len(part) > 3):
                candidates[s.id] = max(candidates.get(s.id, 0), 0.45)

    out: List[dict] = []
    for sid, score in sorted(candidates.items(), key=lambda x: -x[1])[:5]:
        s = db.query(Shipment).filter(Shipment.id == sid).first()
        if s:
            out.append({
                "shipment_id": s.id,
                "shp_id": s.shp_id,
                "supplier": s.supplier,
                "score": round(score, 2),
            })
    return out


@router.get("/{doc_id}/possible-matches")
def possible_matches(doc_id: int, db: Session = Depends(get_db)):
    att = db.query(EmailAttachment).filter(EmailAttachment.id == doc_id).first()
    if not att:
        raise HTTPException(status_code=404, detail="Document not found")
    eu = None
    if att.email_update_id:
        eu = db.query(EmailUpdate).filter(EmailUpdate.id == att.email_update_id).first()
    return {
        "document_id": doc_id,
        "filename": att.filename,
        "candidates": _possible_matches_for(db, att, eu),
    }
