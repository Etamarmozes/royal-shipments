import logging
import os
import uuid
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..config import UPLOADS_DIR
from ..database import get_db
from ..schemas.shipment import ShipmentCreate, ShipmentUpdate, ShipmentRead, ShipmentList
from ..schemas.event import ShipmentEventRead
from ..models import Shipment, ShipmentEvent, EmailAttachment, EmailUpdate, Container
from ..services import shipment_service, event_service, data_quality_service
from ..services.auth_service import require_permission, get_current_user
from ..models import User
from sqlalchemy import or_

router = APIRouter(prefix="/shipments", tags=["shipments"])

log = logging.getLogger("shipments")

PRODUCT_IMG_DIR = UPLOADS_DIR / "product-images"
PRODUCT_IMG_DIR.mkdir(parents=True, exist_ok=True)
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_IMAGE_BYTES = 8 * 1024 * 1024  # 8 MB


@router.get("", response_model=ShipmentList)
def list_shipments(
    archived: Optional[bool] = False,
    search: Optional[str] = None,
    stage: Optional[int] = None,
    delay: Optional[bool] = None,
    customs_broker: Optional[str] = None,
    origin_country: Optional[str] = None,
    paperwork_missing: Optional[bool] = None,
    extra_work_only: Optional[bool] = None,
    category: Optional[str] = None,
    limit: int = Query(200, le=1000),
    offset: int = 0,
    db: Session = Depends(get_db),
):
    return shipment_service.list_shipments(
        db,
        archived=archived,
        search=search,
        stage=stage,
        delay=delay,
        customs_broker=customs_broker,
        origin_country=origin_country,
        paperwork_missing=paperwork_missing,
        extra_work_only=extra_work_only,
        category=category,
        limit=limit,
        offset=offset,
    )


@router.get("/categories/list")
def list_categories():
    """Controlled list of product categories for the UI dropdown."""
    from ..services.category_service import CATEGORIES
    return {"categories": CATEGORIES}


@router.get("/search")
def search_shipments(
    q: Optional[str] = None,
    limit: int = Query(20, le=50),
    include_archived: bool = False,
    db: Session = Depends(get_db),
):
    """Free-text shipment search for the QC reassign modal.

    Searches across: shp_id, supplier, category, goods_description,
    booking_number, bol_number, invoice_number, po_number,
    AND container_number on the shipment's containers.

    Returns a compact summary suitable for a dropdown — never the full row.
    """
    from sqlalchemy import or_
    qry = db.query(Shipment)
    if not include_archived:
        qry = qry.filter(Shipment.archived == False)  # noqa: E712

    q = (q or "").strip()
    if q:
        like = f"%{q}%"
        qry = qry.outerjoin(Container, Container.shipment_id == Shipment.id).filter(
            or_(
                Shipment.shp_id.ilike(like),
                Shipment.supplier.ilike(like),
                Shipment.category.ilike(like),
                Shipment.goods_description.ilike(like),
                Shipment.booking_number.ilike(like),
                Shipment.bol_number.ilike(like),
                Shipment.invoice_number.ilike(like),
                Shipment.po_number.ilike(like),
                Container.container_number.ilike(like),
            )
        ).distinct()

    rows = qry.order_by(Shipment.id.desc()).limit(limit).all()
    out = []
    for s in rows:
        cont_numbers = [c.container_number for c in (s.containers or [])
                        if c.container_number]
        out.append({
            "id": s.id,
            "shp_id": s.shp_id,
            "supplier": s.supplier,
            "category": s.category,
            "goods_description": s.goods_description,
            "po_number": s.po_number,
            "bol_number": s.bol_number,
            "invoice_number": s.invoice_number,
            "container_numbers": cont_numbers,
            "eta_israel": s.eta_israel.isoformat() if s.eta_israel else None,
            "eta_warehouse": s.eta_warehouse.isoformat() if s.eta_warehouse else None,
            "stage_status": s.stage_status,
            "archived": bool(s.archived),
        })
    return {"rows": out, "total": len(out)}


@router.get("/help/supplier-doc")
def supplier_doc():
    """Serve the supplier requirements markdown for in-app help."""
    from ..config import BASE_DIR
    doc_path = BASE_DIR.parent / "docs" / "SUPPLIER_SHIPMENT_DATA_REQUIREMENTS.md"
    if not doc_path.exists():
        raise HTTPException(status_code=404, detail="Supplier doc not found")
    return {
        "title": "Supplier Shipment Data Requirements",
        "markdown": doc_path.read_text(encoding="utf-8"),
        "path": str(doc_path),
    }


@router.get("/{shipment_id}", response_model=ShipmentRead)
def get_shipment(shipment_id: int, db: Session = Depends(get_db)):
    s = shipment_service.get_shipment(db, shipment_id)
    return shipment_service.enrich_shipment(s)


@router.post("", response_model=ShipmentRead)
def create_shipment(
    payload: ShipmentCreate, db: Session = Depends(get_db),
    actor: User = Depends(require_permission("shipment.create")),
):
    s = shipment_service.create_shipment(
        db, payload, created_by=actor.full_name or actor.username,
    )
    return shipment_service.enrich_shipment(s)


@router.put("/{shipment_id}", response_model=ShipmentRead)
def update_shipment(
    shipment_id: int, payload: ShipmentUpdate, db: Session = Depends(get_db),
    actor: User = Depends(require_permission("shipment.update")),
):
    s = shipment_service.update_shipment(
        db, shipment_id, payload,
        updated_by=actor.full_name or actor.username, source="manual",
    )
    return shipment_service.enrich_shipment(s)


@router.delete("/{shipment_id}", response_model=ShipmentRead)
def delete_shipment(
    shipment_id: int, db: Session = Depends(get_db),
    actor: User = Depends(require_permission("shipment.archive")),
):
    s = shipment_service.soft_delete_shipment(
        db, shipment_id, deleted_by=actor.full_name or actor.username,
    )
    return shipment_service.enrich_shipment(s)


@router.post("/{shipment_id}/recalculate-document-status")
def recalculate_document_status(
    shipment_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("document.assign")),
):
    """Re-classify every attachment of this shipment and return the smart
    document-status checklist. Updates classification on each row;
    NEVER mutates shipment fields."""
    s = shipment_service.get_shipment(db, shipment_id)
    from ..services import document_status_service
    return document_status_service.recalculate(db, s)


@router.get("/{shipment_id}/document-status")
def get_document_status(
    shipment_id: int,
    db: Session = Depends(get_db),
):
    """Read-only smart checklist (no re-classification)."""
    s = shipment_service.get_shipment(db, shipment_id)
    from ..services import document_status_service
    return document_status_service.get_status(db, s)


@router.get("/{shipment_id}/data-quality")
def shipment_data_quality(shipment_id: int, db: Session = Depends(get_db)):
    s = shipment_service.get_shipment(db, shipment_id)
    return data_quality_service.shipment_quality(s)


@router.get("/{shipment_id}/documents")
def list_shipment_documents(shipment_id: int, db: Session = Depends(get_db)):
    """Documents for THIS shipment only.

    Returns attachments where:
      - linked_shipment_id == shipment_id   (direct link), OR
      - linked_container_id ∈ this shipment's containers (indirect via container)

    This endpoint exists in addition to GET /documents?shipment_id=X
    for two reasons:
      1. RESTful — the URL itself encodes the scoping, much harder for the
         frontend to accidentally drop the filter.
      2. It also picks up docs that are linked at the container level but
         not at the shipment level (the older endpoint required an
         explicit linked_shipment_id).

    The 404 here means the shipment itself doesn't exist — never returns
    documents from a different shipment.
    """
    s = shipment_service.get_shipment(db, shipment_id)  # raises 404 if missing

    container_ids = [c.id for c in (s.containers or [])]

    q = db.query(EmailAttachment).filter(
        EmailAttachment.archived == False,  # noqa: E712 — hide archived
        or_(
            EmailAttachment.linked_shipment_id == shipment_id,
            EmailAttachment.linked_container_id.in_(container_ids) if container_ids else False,  # noqa: E712
        )
    )
    rows = q.order_by(EmailAttachment.id.desc()).limit(500).all()

    out = []
    for att in rows:
        d = {col.name: getattr(att, col.name) for col in att.__table__.columns}
        # Attribution — useful for debugging / audit trail in the UI
        if att.email_update_id:
            eu = db.query(EmailUpdate).filter(EmailUpdate.id == att.email_update_id).first()
            if eu:
                d["source_email_sender"] = eu.sender
                d["source_email_subject"] = eu.subject
                d["received_at"] = eu.received_at.isoformat() if eu.received_at else None
        # Stamp the shipment so the client can verify scoping at render time
        d["shp_id"] = s.shp_id
        if att.linked_container_id:
            c = db.query(Container).filter(Container.id == att.linked_container_id).first()
            if c:
                d["container_number"] = c.container_number
        out.append(d)
    return out


@router.get("/{shipment_id}/events", response_model=list[ShipmentEventRead])
def shipment_events(shipment_id: int, db: Session = Depends(get_db)):
    return (
        db.query(ShipmentEvent)
        .filter(ShipmentEvent.entity_type == "shipment", ShipmentEvent.entity_id == shipment_id)
        .order_by(ShipmentEvent.changed_at.desc())
        .limit(500)
        .all()
    )


@router.post("/{shipment_id}/product-image")
async def upload_product_image(
    shipment_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("product_image.upload")),
):
    """Upload a product image for the shipment.
    Accepts jpg/jpeg/png/webp up to 8 MB. Replaces any existing image."""
    s = shipment_service.get_shipment(db, shipment_id)
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTS:
        raise HTTPException(
            status_code=400,
            detail=f"סוג קובץ לא נתמך: {ext}. מותר: {', '.join(sorted(ALLOWED_EXTS))}",
        )
    if file.content_type and file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=400, detail=f"סוג mime לא נתמך: {file.content_type}",
        )

    # Read with size limit
    contents = await file.read(MAX_IMAGE_BYTES + 1)
    if len(contents) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="הקובץ חורג מ-8MB")
    if not contents:
        raise HTTPException(status_code=400, detail="קובץ ריק")

    # Save: shipment_id + uuid suffix to prevent caching issues
    fname = f"{s.shp_id}_{uuid.uuid4().hex[:8]}{ext}"
    fpath = PRODUCT_IMG_DIR / fname
    fpath.write_bytes(contents)

    # Delete previous file if exists
    old_path = s.product_image_path
    if old_path:
        try:
            old_full = PRODUCT_IMG_DIR / Path(old_path).name
            if old_full.exists() and old_full != fpath:
                old_full.unlink()
        except Exception as e:
            log.warning("Failed to remove old image %s: %s", old_path, e)

    s.product_image_path = f"product-images/{fname}"
    event_service.log_event(
        db,
        entity_type="shipment", entity_id=s.id,
        action_type="product_image_uploaded",
        new_value=fname,
        changed_by=actor.full_name or actor.username,
        source="manual",
    )
    db.commit()
    db.refresh(s)
    log.info("Shipment %s: product image saved to %s (%d bytes)", s.shp_id, fname, len(contents))
    return {
        "ok": True,
        "shipment_id": s.id,
        "product_image_path": s.product_image_path,
        "size_bytes": len(contents),
    }


@router.delete("/{shipment_id}/product-image")
def delete_product_image(
    shipment_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("product_image.upload")),
):
    s = shipment_service.get_shipment(db, shipment_id)
    if not s.product_image_path:
        return {"ok": True, "message": "No image to delete"}
    try:
        old_full = PRODUCT_IMG_DIR / Path(s.product_image_path).name
        if old_full.exists():
            old_full.unlink()
    except Exception as e:
        log.warning("Failed to remove image: %s", e)
    s.product_image_path = None
    event_service.log_event(
        db, entity_type="shipment", entity_id=s.id,
        action_type="product_image_deleted",
        changed_by=actor.full_name or actor.username, source="manual",
    )
    db.commit()
    return {"ok": True}


@router.get("/{shipment_id}/product-image")
def serve_product_image(shipment_id: int, db: Session = Depends(get_db)):
    """Serve the shipment's product image."""
    s = shipment_service.get_shipment(db, shipment_id)
    if not s.product_image_path:
        raise HTTPException(status_code=404, detail="No image")
    fpath = PRODUCT_IMG_DIR / Path(s.product_image_path).name
    if not fpath.exists():
        raise HTTPException(status_code=404, detail="File missing on disk")
    return FileResponse(str(fpath))
