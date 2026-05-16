"""Existing Shipment Data Review.

Surface every shipment in the DB with diagnostic info that lets the user
decide which records are demo/test (safe to delete) vs real (must keep).

NEVER deletes anything automatically. The user marks `is_test_data` first,
then explicitly invokes `purge-test-data` to delete only the marked rows.
"""
import re
from pathlib import Path
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from ..config import UPLOADS_DIR
from ..database import get_db
from ..models import Shipment, Container, EmailAttachment, EmailUpdate, User
from ..services import event_service
from ..services.auth_service import require_permission

router = APIRouter(prefix="/data-review", tags=["data-review"])


# ---- Heuristic: which existing rows look like demo/test? ----
# Used ONLY as a suggestion in the review screen. Never auto-applied.
DEMO_SHP_PREFIXES = {"SHP-006", "SHP-007", "SHP-008", "SHP-009", "SHP-010", "SHP-011"}
DEMO_SUPPLIER_HINTS = (
    "test", "demo", "sample", "lorem", "foo", "bar",
    "TEST_OVERRIDE",
)


def _looks_like_demo(s: Shipment) -> tuple[bool, list[str]]:
    """Return (is_demo, reasons[]). Pure function — no DB writes."""
    reasons: list[str] = []
    if s.shp_id in DEMO_SHP_PREFIXES:
        reasons.append(f"shp_id {s.shp_id} matches seed-data range (SHP-006…SHP-011)")
    sup = (s.supplier or "").lower()
    for hint in DEMO_SUPPLIER_HINTS:
        if hint.lower() in sup:
            reasons.append(f"supplier contains '{hint}'")
            break
    if s.is_test_data:
        reasons.append("explicitly flagged is_test_data=true")
    return (bool(reasons), reasons)


@router.get("")
def list_data_review(
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("shipment.read")),
):
    """One row per shipment with: identity, source, container count,
    suspected-demo flag, and the supplier/category for human review."""
    rows = (
        db.query(Shipment)
        .options(joinedload(Shipment.containers))
        .order_by(Shipment.id.asc())
        .all()
    )
    out: List[Dict[str, Any]] = []
    for s in rows:
        suspected, reasons = _looks_like_demo(s)
        containers = s.containers or []
        out.append({
            "id": s.id,
            "shp_id": s.shp_id,
            "supplier": s.supplier,
            "category": s.category,
            "goods_description": s.goods_description,
            "current_stage": s.current_stage,
            "container_count": len(containers),
            "container_numbers": [c.container_number for c in containers if c.container_number],
            "creation_source": s.creation_source,        # legacy field
            "data_source": s.data_source,                # new explicit field
            "is_test_data": bool(s.is_test_data),
            "suspected_demo": suspected,
            "demo_reasons": reasons,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "updated_at": s.updated_at.isoformat() if s.updated_at else None,
            "updated_by": s.updated_by,
            "last_update_source": s.last_update_source,
            "archived": bool(s.archived),
        })
    summary = {
        "total": len(out),
        "suspected_demo": sum(1 for r in out if r["suspected_demo"]),
        "marked_test": sum(1 for r in out if r["is_test_data"]),
        "archived": sum(1 for r in out if r["archived"]),
        "real": sum(1 for r in out if not r["suspected_demo"] and not r["is_test_data"]),
    }
    return {"summary": summary, "rows": out}


class FlagRequest(BaseModel):
    is_test_data: bool
    data_source: Optional[str] = None  # demo / manual / excel / email / imported
    reason: Optional[str] = None


@router.patch("/{shipment_id}")
def flag_shipment(
    shipment_id: int, payload: FlagRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("shipment.update")),
):
    """Mark/unmark a shipment as test data + (optionally) tag its data_source.
    Never touches business fields. Logs to ShipmentEvent for audit."""
    s = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Shipment not found")

    old_test = bool(s.is_test_data)
    old_source = s.data_source
    s.is_test_data = bool(payload.is_test_data)
    if payload.data_source is not None:
        if payload.data_source not in ("demo", "manual", "excel", "email", "imported", ""):
            raise HTTPException(status_code=400,
                                detail=f"data_source לא חוקי: {payload.data_source}")
        s.data_source = payload.data_source or None

    actor_name = actor.full_name or actor.username
    if old_test != s.is_test_data:
        event_service.log_event(
            db, entity_type="shipment", entity_id=s.id,
            action_type="flag_test_data",
            old_value=str(old_test), new_value=str(s.is_test_data),
            field_changed="is_test_data",
            changed_by=actor_name, source="manual",
            note=payload.reason,
        )
    if old_source != s.data_source:
        event_service.log_event(
            db, entity_type="shipment", entity_id=s.id,
            action_type="set_data_source",
            old_value=old_source, new_value=s.data_source,
            field_changed="data_source",
            changed_by=actor_name, source="manual",
        )
    db.commit()
    return {
        "id": s.id, "shp_id": s.shp_id,
        "is_test_data": bool(s.is_test_data),
        "data_source": s.data_source,
    }


class BulkFlagRequest(BaseModel):
    ids: List[int]
    is_test_data: bool
    data_source: Optional[str] = None


@router.patch("/bulk-flag")
def bulk_flag(
    payload: BulkFlagRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("shipment.update")),
):
    """Mark/unmark many shipments at once (e.g. flag all suspected demos)."""
    affected = 0
    for sid in payload.ids:
        s = db.query(Shipment).filter(Shipment.id == sid).first()
        if not s:
            continue
        s.is_test_data = bool(payload.is_test_data)
        if payload.data_source:
            s.data_source = payload.data_source
        affected += 1
    actor_name = actor.full_name or actor.username
    event_service.log_event(
        db, entity_type="system", entity_id=0,
        action_type="bulk_flag_test_data",
        new_value=f"{affected} rows → is_test_data={payload.is_test_data}",
        changed_by=actor_name, source="manual",
    )
    db.commit()
    return {"affected": affected, "is_test_data": payload.is_test_data}


class PurgeRequest(BaseModel):
    confirm: str  # must be the literal "DELETE"
    only_test_data: bool = True   # safety: never delete non-test rows


# =====================================================================
# Document Assignment Review — diagnostic, NEVER mutates
# =====================================================================

_CN_RX = re.compile(r"\b([A-Z]{4}\s?\d{7})\b")
_SHP_RX = re.compile(r"\b(SHP[-\s]?\d{3,4})\b", re.IGNORECASE)
_CART_RX = re.compile(r"\((\d{1,5})\s*(?:CTN|CTNS|cartons?)\)", re.IGNORECASE)


def _audit_one_attachment(
    att: EmailAttachment,
    cn_to_shipment: Dict[str, int],
    shipment_lookup: Dict[int, Shipment],
    container_lookup: Dict[int, Container],
    docs_dir: Path,
) -> Dict[str, Any]:
    fname = (att.filename or "")
    fname_upper = fname.upper()

    # Extract identifiers from filename
    cn_in_name = list({m.replace(" ", "") for m in _CN_RX.findall(fname_upper)})
    shp_in_name = list({m.upper().replace(" ", "-") for m in _SHP_RX.findall(fname)})
    cart_in_name = _CART_RX.findall(fname)

    flags: List[str] = []
    suggested_shp_id: Optional[int] = None
    confidence: float = 0.0

    # Resolve currently assigned
    assigned = shipment_lookup.get(att.linked_shipment_id) if att.linked_shipment_id else None
    assigned_container = container_lookup.get(att.linked_container_id) if att.linked_container_id else None

    # Hard signal 1: filename mentions a container that belongs to a DIFFERENT shipment
    for cn in cn_in_name:
        real_shp = cn_to_shipment.get(cn)
        if real_shp and att.linked_shipment_id and real_shp != att.linked_shipment_id:
            real_shp_obj = shipment_lookup.get(real_shp)
            flags.append(
                f"שם הקובץ מציין מכולה {cn} ששייכת ל-{real_shp_obj.shp_id if real_shp_obj else f'#{real_shp}'} "
                f"(לא {assigned.shp_id if assigned else f'#{att.linked_shipment_id}'})"
            )
            suggested_shp_id = real_shp
            confidence = max(confidence, 0.95)

    # Hard signal 2: filename has SHP-XXX that doesn't match assignment
    for sname in shp_in_name:
        canonical = sname.replace(" ", "-")
        if not canonical.startswith("SHP-"):
            canonical = "SHP-" + canonical.lstrip("SHP")
        target = next((s for s in shipment_lookup.values() if s.shp_id == canonical), None)
        if target and assigned and target.id != assigned.id:
            flags.append(
                f"שם הקובץ מציין {canonical} (לא {assigned.shp_id})"
            )
            suggested_shp_id = target.id
            confidence = max(confidence, 0.95)

    # Soft signal: cartons hint
    if cart_in_name and assigned:
        cart_n = int(cart_in_name[0])
        ship_carton_set = {c.boxes_total for c in (assigned.containers or []) if c.boxes_total}
        if ship_carton_set and cart_n not in ship_carton_set:
            # Try to find a different shipment whose container matches
            cart_to_cont = {c.boxes_total: c for c in container_lookup.values() if c.boxes_total}
            cont = cart_to_cont.get(cart_n)
            if cont and cont.shipment_id != assigned.id:
                target = shipment_lookup.get(cont.shipment_id)
                flags.append(
                    f"שם הקובץ אומר {cart_n} CTN — תואם ל-{target.shp_id if target else f'#{cont.shipment_id}'}, "
                    f"לא ל-{assigned.shp_id}"
                )
                if not suggested_shp_id:
                    suggested_shp_id = cont.shipment_id
                    confidence = max(confidence, 0.6)

    # File-on-disk check
    file_exists = False
    if att.file_path:
        fpath = docs_dir / Path(att.file_path).name
        try:
            file_exists = fpath.exists() and fpath.stat().st_size > 0
        except Exception:
            file_exists = False

    # Action recommendation (NEVER applied automatically)
    if flags:
        action = "needs_review"
    elif att.linked_shipment_id is None:
        action = "needs_review"  # unassigned
    else:
        action = "keep"

    suggested_shp = shipment_lookup.get(suggested_shp_id) if suggested_shp_id else None

    return {
        "id": att.id,
        "filename": fname,
        "linked_shipment_id": att.linked_shipment_id,
        "linked_shipment_shp_id": assigned.shp_id if assigned else None,
        "linked_container_id": att.linked_container_id,
        "linked_container_number": assigned_container.container_number if assigned_container else None,
        "email_update_id": att.email_update_id,
        "file_exists": file_exists,
        "suspected_wrong": bool(flags),
        "suggested_shipment_id": suggested_shp_id,
        "suggested_shp_id": suggested_shp.shp_id if suggested_shp else None,
        "reasons": flags,
        "confidence": round(confidence, 2),
        "action": action,
        "document_type": att.document_type,
    }


@router.get("/documents")
def document_assignment_review(
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("shipment.read")),
):
    """Document Assignment Review — diagnostic only, NEVER mutates.

    For every attachment in the DB, cross-reference its filename + the
    shipment it's currently linked to and look for contradictions:
      - filename names a container that belongs to a different shipment
      - filename names a different SHP-ID
      - cartons-in-filename matches a container in a different shipment

    Output marks each attachment as keep / needs_review with reasons +
    suggested correct shipment + confidence. Reassignment is NOT done
    here — the user reviews the report and decides what to do manually
    via the existing /documents/{id}/assign endpoint.
    """
    atts = db.query(EmailAttachment).order_by(EmailAttachment.id.asc()).all()
    shipments = db.query(Shipment).options(joinedload(Shipment.containers)).all()
    containers = db.query(Container).all()
    docs_dir = UPLOADS_DIR / "documents"

    cn_to_shipment = {c.container_number: c.shipment_id
                      for c in containers if c.container_number}
    shipment_lookup = {s.id: s for s in shipments}
    container_lookup = {c.id: c for c in containers}

    rows = [_audit_one_attachment(a, cn_to_shipment, shipment_lookup,
                                   container_lookup, docs_dir)
            for a in atts]

    summary = {
        "total": len(rows),
        "linked": sum(1 for r in rows if r["linked_shipment_id"] is not None),
        "unassigned": sum(1 for r in rows if r["linked_shipment_id"] is None),
        "suspected_wrong": sum(1 for r in rows if r["suspected_wrong"]),
        "missing_on_disk": sum(1 for r in rows if r["linked_shipment_id"] is not None
                                                and not r["file_exists"]),
        "needs_review": sum(1 for r in rows if r["action"] == "needs_review"),
    }
    return {"summary": summary, "rows": rows}


@router.post("/purge-test-data")
def purge_test_data(
    payload: PurgeRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("shipment.delete")),
):
    """Hard-delete every shipment marked is_test_data=true.
    Requires admin role + literal confirm='DELETE' string in the body.
    Cascades to containers (SQLAlchemy 'all, delete-orphan')."""
    if payload.confirm != "DELETE":
        raise HTTPException(
            status_code=400,
            detail="פעולה זו דורשת אישור מפורש: שלח 'confirm': 'DELETE'",
        )
    if not payload.only_test_data:
        raise HTTPException(
            status_code=400,
            detail="רק רשומות עם is_test_data=true ניתנות למחיקה דרך נתיב זה. "
                   "הגדר only_test_data=true.",
        )

    rows = db.query(Shipment).filter(Shipment.is_test_data == True).all()  # noqa: E712
    deleted_ids = [(s.id, s.shp_id) for s in rows]
    for s in rows:
        db.delete(s)
    actor_name = actor.full_name or actor.username
    event_service.log_event(
        db, entity_type="system", entity_id=0,
        action_type="purge_test_data",
        new_value=f"deleted {len(deleted_ids)} test shipments",
        changed_by=actor_name, source="manual",
        note=str(deleted_ids[:20]),
    )
    db.commit()
    return {"deleted": len(deleted_ids), "deleted_ids": deleted_ids}
