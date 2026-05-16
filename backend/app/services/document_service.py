"""Shipment / container document storage.

EmailAttachment is the underlying model — it stores files that come from
emails (gmail) and their links to shipments/containers. The schema also
supports manual uploads and Drive (later).

Responsibilities:
- guess_document_type(filename, subject, body) — heuristic classification
- attempt_link_to_shipment(db, attachment, sender, body, parsed_fields) — match
  to a Shipment/Container by SHP-ID, container, booking, BOL, invoice, PO
- ensure_required_documents_alerts(db, shipment) — alert when PL / Invoice / BL missing
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from sqlalchemy.orm import Session

from ..config import UPLOADS_DIR
from ..models import EmailAttachment, Shipment, Container
from . import alert_service

log = logging.getLogger("documents")

DOCS_DIR = UPLOADS_DIR / "documents"
DOCS_DIR.mkdir(parents=True, exist_ok=True)


# Filename patterns → document_type
_FILENAME_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"packing[\s_\-]?list|packinglist|\bpl\b", re.IGNORECASE), "packing_list"),
    (re.compile(r"\binvoice\b|\binv\b", re.IGNORECASE), "invoice"),
    (re.compile(r"bill[\s_\-]?of[\s_\-]?lading", re.IGNORECASE), "bl"),
    (re.compile(r"\bbol\b|\bb[\s_]?of[\s_]?l\b", re.IGNORECASE), "bol"),
    (re.compile(r"\bbl\b", re.IGNORECASE), "bl"),
    (re.compile(r"booking[\s_\-]?confirmation|booking[\s_\-]?conf", re.IGNORECASE), "booking_confirmation"),
    (re.compile(r"\bbooking\b", re.IGNORECASE), "booking_confirmation"),
    (re.compile(r"customs|מכס", re.IGNORECASE), "customs"),
]


def guess_document_type(filename: Optional[str] = None, subject: Optional[str] = None, body: Optional[str] = None) -> str:
    """Best-effort classification. Returns one of:
    packing_list / invoice / bl / bol / booking_confirmation / customs / other"""
    haystacks = [s for s in (filename, subject, body) if s]
    blob = " ".join(haystacks)
    for rx, dt in _FILENAME_RULES:
        if rx.search(blob):
            return dt
    return "other"


_FILE_CONTAINER_RX = re.compile(r"\b([A-Z]{4}\s?\d{7})\b")
_FILE_SHP_RX = re.compile(r"\b(SHP[-\s]?\d{3,4})\b", re.IGNORECASE)
_FILE_CARTONS_RX = re.compile(r"\((\d{1,5})\s*(?:CTN|CTNS|cartons?)\)", re.IGNORECASE)

# Google Drive / Docs link detection in email bodies
_DRIVE_LINK_RX = re.compile(
    r"(https?://(?:drive\.google\.com|docs\.google\.com)/[^\s<>\"]+)",
    re.IGNORECASE,
)


def find_drive_links(text: Optional[str]) -> List[str]:
    """Extract Google Drive / Docs URLs from a chunk of email body text."""
    if not text:
        return []
    links = list({m for m in _DRIVE_LINK_RX.findall(text)})
    return links


def guess_doc_type_from_link(link: str) -> str:
    """Heuristic from URL/filename hints in a Drive link."""
    low = link.lower()
    if "packing" in low or "/pl-" in low or "/pl_" in low: return "packing_list"
    if "invoice" in low or "/inv-" in low or "/inv_" in low: return "invoice"
    if "/bl-" in low or "/bol-" in low or "lading" in low: return "bl"
    if "booking" in low: return "booking_confirmation"
    return "other"


def _scan_filename_for_identifiers(filename: str) -> Dict[str, Any]:
    """Look for SHP-IDs, container numbers, carton counts in a filename
    like 'EX2550603914 ROYAL LINEN ... (939 CTN)-1st.xls'."""
    out: Dict[str, Any] = {}
    if not filename:
        return out
    if (m := _FILE_SHP_RX.search(filename)):
        out["shipment_id"] = m.group(1).upper().replace(" ", "-")
    container_matches = list({m.replace(" ", "") for m in _FILE_CONTAINER_RX.findall(filename.upper())})
    if container_matches:
        out["container_numbers"] = container_matches
    if (m := _FILE_CARTONS_RX.search(filename)):
        try:
            out["cartons"] = int(m.group(1))
        except ValueError:
            pass
    return out


def attempt_link_to_shipment(
    db: Session,
    *,
    parsed_fields: Optional[Dict[str, Any]] = None,
    sender: Optional[str] = None,
    filename: Optional[str] = None,
) -> Tuple[Optional[int], Optional[int]]:
    """Try to find a shipment + container to link this document to.

    Sources (in order):
      1. Already-parsed email fields (parsed_fields)
      2. Identifiers scanned out of the attachment's filename
      3. Carton-count heuristic (filename has '(939 CTN)' → match Container.boxes_total=939)
    """
    f: Dict[str, Any] = {}
    if parsed_fields:
        f = (
            parsed_fields["extracted_fields"]
            if isinstance(parsed_fields, dict) and "extracted_fields" in parsed_fields
            else parsed_fields
        ) or {}

    # Layer in filename clues
    if filename:
        fn_clues = _scan_filename_for_identifiers(filename)
        for k, v in fn_clues.items():
            if not f.get(k):
                f[k] = v
            elif k == "container_numbers":
                # union
                f["container_numbers"] = list(set((f.get("container_numbers") or []) + v))

    # SHP-ID
    if (shp := f.get("shipment_id")):
        s = db.query(Shipment).filter(Shipment.shp_id == shp).first()
        if s:
            return s.id, None

    # Container number
    for cn in (f.get("container_numbers") or []):
        c = db.query(Container).filter(Container.container_number == cn).first()
        if c:
            return c.shipment_id, c.id

    # Booking / BOL / Invoice / PO
    for col, key in [
        ("booking_number", "booking_number"),
        ("bol_number", "bl_number"),
        ("invoice_number", "invoice_number"),
        ("po_number", "po_number"),
    ]:
        v = f.get(key)
        if not v:
            continue
        s = db.query(Shipment).filter(getattr(Shipment, col) == v).first()
        if s:
            return s.id, None

    # Last resort: cartons hint from filename matched against Container.boxes_total
    if (cart := f.get("cartons")):
        c = db.query(Container).filter(Container.boxes_total == cart).first()
        if c:
            return c.shipment_id, c.id

    return None, None


def required_doc_types() -> list[str]:
    return ["packing_list", "invoice", "bl"]


def required_documents_status(db: Session, shipment: Shipment) -> Dict[str, Any]:
    """For a shipment, return which required document types are present/missing."""
    rows = db.query(EmailAttachment).filter(
        EmailAttachment.linked_shipment_id == shipment.id
    ).all()
    types_present: set[str] = set()
    for r in rows:
        if r.document_type:
            types_present.add(r.document_type)
    # treat 'bol' as a satisfier for 'bl' (and vice-versa)
    if "bol" in types_present:
        types_present.add("bl")
    if "bl" in types_present:
        types_present.add("bol")
    if "booking_confirmation" in types_present:
        types_present.add("bl")  # booking can stand in early
    missing = [t for t in required_doc_types() if t not in types_present]
    return {
        "present": sorted(types_present),
        "missing": missing,
        "is_complete": not missing,
        "count": len(rows),
    }


def alert_missing_docs(db: Session, shipment: Shipment) -> None:
    """Create soft alerts for missing required documents on a late-stage shipment."""
    if (shipment.current_stage or 0) < 5:
        return
    status = required_documents_status(db, shipment)
    for missing_type in status["missing"]:
        alert_service.create_alert(
            db,
            alert_type=f"missing_document_{missing_type}",
            title=f"חסר מסמך {missing_type} — {shipment.shp_id}",
            description=f"לא קיים {missing_type} עבור {shipment.shp_id}",
            severity="medium",
            shipment_id=shipment.id,
        )


def doc_filename_on_disk(att: EmailAttachment) -> Optional[Path]:
    if not att.file_path:
        return None
    return DOCS_DIR / Path(att.file_path).name
