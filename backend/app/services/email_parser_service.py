"""Heuristic email parser — regex + simple rules. No AI.

Public API:
    parse_email(email: EmailUpdate) -> ParsedResult

ParsedResult.detection_type ∈ {"new_shipment", "update", "delay", "unknown"}
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from dateutil import parser as dateparser

log = logging.getLogger("parser")


# ---------------------------------------------------------------------
# Regexes
# ---------------------------------------------------------------------

CONTAINER_RX = re.compile(r"\b([A-Z]{4}\s?\d{7})\b")
SHP_RX = re.compile(r"\bSHP[-\s]?(\d{3,4})\b", re.IGNORECASE)

BOOKING_RX = re.compile(
    r"(?:booking(?:\s*(?:no|number|ref|reference|#))?|בוקינג)[:\s#]+([A-Z0-9][A-Z0-9\-]{4,})",
    re.IGNORECASE,
)
BOL_RX = re.compile(
    r"(?:b[\.\/]?o[\.\/]?l|bill\s+of\s+lading|bl|שטר\s+מטען)[:\s#]+([A-Z0-9][A-Z0-9\-]{4,})",
    re.IGNORECASE,
)
INVOICE_RX = re.compile(
    r"(?:invoice(?:\s*(?:no|number|#))?|חשבונית)[:\s#]+([A-Z0-9][A-Z0-9\-]{3,})",
    re.IGNORECASE,
)
PO_RX = re.compile(
    r"(?:p[\.\/]?o(?:\s*(?:no|number|#))?|הזמנה)[:\s#]+([A-Z0-9][A-Z0-9\-]{3,})",
    re.IGNORECASE,
)

# Date pattern — DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY (2 or 4 digit year)
_DATE = r"(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})"

# ETA Israel — explicit phrasing
ETA_ISRAEL_RX = re.compile(
    rf"(?:ETA[\s]*(?:to[\s]+)?(?:Israel|IL|Ashdod|Haifa)|הגעה[\s]+ל?(?:ארץ|ישראל|אשדוד|חיפה))[:\s]*{_DATE}",
    re.IGNORECASE,
)
# ETA Warehouse
ETA_WAREHOUSE_RX = re.compile(
    rf"(?:ETA[\s]+warehouse|warehouse[\s]+ETA|הגעה[\s]+ל?מחסן)[:\s]*{_DATE}",
    re.IGNORECASE,
)
# ETA Port
ETA_PORT_RX = re.compile(
    rf"(?:ETA[\s]+port|port[\s]+ETA|הגעה[\s]+ל?נמל)[:\s]*{_DATE}",
    re.IGNORECASE,
)
# Generic ETA fallback
ETA_GENERIC_RX = re.compile(
    rf"(?:ETA|expected\s+arrival|הגעה\s+צפויה|יגיע)[:\s]+{_DATE}",
    re.IGNORECASE,
)
# ETD
ETD_RX = re.compile(
    rf"(?:ETD|expected\s+departure|יציאה\s+צפויה|הפלגה)[:\s]+{_DATE}",
    re.IGNORECASE,
)

# Supplier — usually appears in "From:" sender or as "Supplier:" / "Vendor:"
SUPPLIER_RX = re.compile(
    r"(?:supplier|vendor|shipper|exporter|ספק|יצואן)[:\s]+([A-Za-z0-9א-ת][A-Za-z0-9א-ת \-&\.\/]{2,60})",
    re.IGNORECASE,
)

# CBM — two patterns:
#   labeled: "CBM: 43.44" / "Volume: 43.44" / "נפח: 43.44"
#   inline:  "43.44 CBM" / "43.44 m³" — requires whitespace BEFORE the number
#            so it doesn't pick up digits from container numbers etc.
CBM_LABELED_RX = re.compile(
    r"(?:\bCBM|\bvolume|\bנפח)[:\s]+(\d+(?:[\.,]\d+)?)",
    re.IGNORECASE,
)
CBM_INLINE_RX = re.compile(
    r"(?<!\w)(\d+(?:[\.,]\d+)?)\s+(?:CBM|m³|m3|cu\.?\s*m\.?)\b",
    re.IGNORECASE,
)
# Weight (kg)
WEIGHT_RX = re.compile(
    r"(?:gross\s+weight|net\s+weight|weight|משקל)[:\s]+(\d{1,3}(?:[,\s]\d{3})*(?:\.\d+)?)\s*(?:kg|KG|kgs|kilogram)",
    re.IGNORECASE,
)
# Quantity / cartons
QTY_RX = re.compile(
    r"(\d{1,6}(?:[,\s]\d{3})*)\s*(?:cartons?|boxes?|cases?|pcs|units?|קופסאות|חבילות)",
    re.IGNORECASE,
)

DELAY_KEYWORDS = [
    "delay", "delayed", "delaying", "postpone", "postponed", "rescheduled",
    "עיכוב", "מתעכב", "התעכב", "נדחה",
]
NEW_SHIPMENT_KEYWORDS = [
    "booking confirmation", "new shipment", "new order", "shipping order",
    "shipment notification", "shipment booking",
    "אישור הזמנה", "הזמנה חדשה", "אישור הפלגה", "אישור משלוח",
]


# ---------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------

@dataclass
class ExtractedFields:
    shipment_id: Optional[str] = None              # SHP-XXX
    container_numbers: List[str] = field(default_factory=list)
    booking_number: Optional[str] = None
    bl_number: Optional[str] = None
    invoice_number: Optional[str] = None
    po_number: Optional[str] = None
    eta_israel: Optional[date] = None
    eta_warehouse: Optional[date] = None
    eta_port: Optional[date] = None
    etd: Optional[date] = None
    supplier: Optional[str] = None
    cbm: Optional[float] = None
    weight_kg: Optional[float] = None
    cartons: Optional[int] = None
    delay_detected: bool = False
    looks_like_new_shipment: bool = False

    def to_jsonable(self) -> Dict[str, Any]:
        d = asdict(self)
        for k, v in list(d.items()):
            if isinstance(v, (date, datetime)):
                d[k] = v.isoformat()
        # Drop empty/null fields for compactness
        return {k: v for k, v in d.items() if v not in (None, [], False, 0.0)}


@dataclass
class ParsedResult:
    detection_type: str                  # "new_shipment" | "update" | "delay" | "unknown"
    confidence_score: float              # 0.0 - 1.0
    extracted_fields: ExtractedFields
    summary: str                         # short human-readable string

    def to_jsonable(self) -> Dict[str, Any]:
        return {
            "detection_type": self.detection_type,
            "confidence_score": self.confidence_score,
            "summary": self.summary,
            "extracted_fields": self.extracted_fields.to_jsonable(),
        }


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def _parse_date(s: str) -> Optional[date]:
    if not s:
        return None
    try:
        d = dateparser.parse(s.strip(), dayfirst=True, fuzzy=True)
        return d.date()
    except Exception:
        return None


def _parse_number(s: str) -> Optional[float]:
    if not s:
        return None
    cleaned = s.replace(",", "").replace(" ", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


_SHP_ID_RX = re.compile(r"^SHP-?\d{3,}$", re.IGNORECASE)
_CONTAINER_RX_FULL = re.compile(r"^[A-Z]{4}\d{7}$")  # ISO 6346 container number


def _is_id_like(s: Optional[str], *, allow_shp: bool = False, allow_container: bool = False) -> bool:
    """An ID-ish value should be 5+ chars and contain at least one digit.

    Filters out false positives:
    - Words like 'Confirmation' captured after 'Booking' (no digits → fail)
    - SHP-IDs captured as booking/BOL/invoice/PO (separate field)
    - Container numbers captured as booking (separate field)
    """
    if not s or len(s) < 5:
        return False
    if not any(c.isdigit() for c in s):
        return False
    if not allow_shp and _SHP_ID_RX.match(s):
        return False
    if not allow_container and _CONTAINER_RX_FULL.match(s.replace(" ", "")):
        return False
    return True


_NOREPLY_PATTERNS = ("noreply", "no-reply", "no_reply", "donotreply", "do-not-reply", "mailer-daemon")
_GENERIC_SENDERS = {"google", "google play", "facebook", "linkedin", "microsoft", "github", "apple", "amazon"}


def _supplier_from_sender(sender: Optional[str]) -> Optional[str]:
    """If sender header looks like 'Royal Vendor Ltd <ops@royal.com>', extract
    the display name — but only for senders that plausibly look like a real
    business/supplier, not a generic platform / noreply address."""
    if not sender:
        return None
    # 'Display Name <email@x.com>'
    m = re.match(r"^\s*(.+?)\s*<([^>]+)>\s*$", sender)
    if not m:
        return None
    name = m.group(1).strip(' "\'')
    address = m.group(2).strip().lower()
    name_low = name.lower().strip()

    if len(name) < 3:
        return None
    # Reject if the EMAIL ADDRESS or display name signals automated/generic
    if any(p in address for p in _NOREPLY_PATTERNS):
        return None
    if any(p in name_low for p in _NOREPLY_PATTERNS):
        return None
    if name_low in _GENERIC_SENDERS:
        return None
    return name


# ---------------------------------------------------------------------
# Field extraction (text-only)
# ---------------------------------------------------------------------

def _extract_fields(subject: str, body: str, sender: Optional[str] = None) -> ExtractedFields:
    text = f"{subject}\n{body}"
    text_low = text.lower()
    fields = ExtractedFields()

    m = SHP_RX.search(text)
    if m:
        fields.shipment_id = f"SHP-{m.group(1).zfill(3)}"

    fields.container_numbers = sorted({
        m.replace(" ", "") for m in CONTAINER_RX.findall(text)
    })

    # Try all matches for each ID-like field — pick the first that
    # actually looks like an ID (has digits, ≥5 chars). Avoids picking up
    # words like "confirmation" that follow the keyword "Booking".
    for rx, attr in [
        (BOOKING_RX, "booking_number"),
        (BOL_RX, "bl_number"),
        (INVOICE_RX, "invoice_number"),
        (PO_RX, "po_number"),
    ]:
        for candidate in rx.findall(text):
            val = candidate.strip()
            if _is_id_like(val):
                setattr(fields, attr, val)
                break

    # Dates: try specific labels first, then generic
    if (m := ETA_ISRAEL_RX.search(text)):
        fields.eta_israel = _parse_date(m.group(1))
    if (m := ETA_WAREHOUSE_RX.search(text)):
        fields.eta_warehouse = _parse_date(m.group(1))
    if (m := ETA_PORT_RX.search(text)):
        fields.eta_port = _parse_date(m.group(1))
    if not fields.eta_israel and (m := ETA_GENERIC_RX.search(text)):
        fields.eta_israel = _parse_date(m.group(1))
    if (m := ETD_RX.search(text)):
        fields.etd = _parse_date(m.group(1))

    # Supplier: prefer explicit "Supplier:" tag, fall back to sender display name
    if (m := SUPPLIER_RX.search(text)):
        fields.supplier = m.group(1).strip(" .,;:\"'")
    elif (s := _supplier_from_sender(sender)):
        fields.supplier = s

    # CBM, Weight, Qty
    cbm_match = CBM_LABELED_RX.search(text) or CBM_INLINE_RX.search(text)
    if cbm_match:
        fields.cbm = _parse_number(cbm_match.group(1))
    if (m := WEIGHT_RX.search(text)):
        fields.weight_kg = _parse_number(m.group(1))
    if (m := QTY_RX.search(text)):
        n = _parse_number(m.group(1))
        if n is not None:
            fields.cartons = int(n)

    # Flags
    fields.delay_detected = any(k in text_low for k in DELAY_KEYWORDS)
    fields.looks_like_new_shipment = any(k.lower() in text_low for k in NEW_SHIPMENT_KEYWORDS)

    return fields


# ---------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------

def _strong_id_present(f: ExtractedFields) -> bool:
    return bool(
        f.shipment_id or f.container_numbers
        or f.booking_number or f.bl_number
    )


def _classify(f: ExtractedFields, has_match: bool) -> tuple[str, float]:
    """Returns (detection_type, confidence_score)."""
    if has_match and f.delay_detected:
        return "delay", 0.85
    if has_match:
        return "update", 0.85
    if f.delay_detected and _strong_id_present(f):
        # Delay mention with IDs that didn't match — still likely a delay update on something
        return "delay", 0.55
    if f.looks_like_new_shipment and _strong_id_present(f):
        return "new_shipment", 0.7
    if _strong_id_present(f):
        # Has shipping IDs but couldn't classify intent — treat as new shipment for review
        return "new_shipment", 0.5
    return "unknown", 0.2


def _summarize(f: ExtractedFields, detection_type: str) -> str:
    bits: List[str] = []
    if f.shipment_id:
        bits.append(f.shipment_id)
    elif f.container_numbers:
        bits.append("מכולה " + ", ".join(f.container_numbers[:2]))
    if f.eta_israel:
        bits.append(f"ETA לארץ {f.eta_israel}")
    if f.eta_warehouse:
        bits.append(f"ETA מחסן {f.eta_warehouse}")
    if f.delay_detected:
        bits.append("⚠️ עיכוב")
    if f.supplier:
        bits.append(f.supplier)
    head = {
        "update": "עדכון",
        "delay": "עיכוב",
        "new_shipment": "משלוח חדש",
        "unknown": "לא רלוונטי",
    }.get(detection_type, "מייל")
    return f"{head}: " + " · ".join(bits) if bits else head


# ---------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------

def parse_email(email, *, extra_text: str = "", has_match: Optional[bool] = None) -> ParsedResult:
    """Parse an EmailUpdate object. Returns ParsedResult.

    Args:
        email: EmailUpdate ORM row (or duck-typed object with .subject /
            .full_body_text / .body_excerpt / .sender)
        extra_text: optional extra text to fold into the parser input —
            this is the seam for PDF/Drive content (next phase).
        has_match: optional override. If None, the caller is expected to
            run match_existing_shipment(...) on the result and reclassify
            via reclassify_with_match(). Pass True/False here only when
            you've already determined match status.
    """
    subject = getattr(email, "subject", "") or ""
    body = getattr(email, "full_body_text", None) or getattr(email, "body_excerpt", "") or ""
    sender = getattr(email, "sender", None)

    parser_input = body
    if extra_text:
        parser_input = f"{body}\n\n--- attachment ---\n{extra_text}"

    fields = _extract_fields(subject, parser_input, sender=sender)

    detection_type, confidence = _classify(fields, has_match=bool(has_match))
    summary = _summarize(fields, detection_type)

    log.info(
        "parse_email: type=%s conf=%.2f shp=%s containers=%s eta_il=%s delay=%s",
        detection_type, confidence, fields.shipment_id,
        fields.container_numbers, fields.eta_israel, fields.delay_detected,
    )

    return ParsedResult(
        detection_type=detection_type,
        confidence_score=confidence,
        extracted_fields=fields,
        summary=summary,
    )


def reclassify_with_match(parsed: ParsedResult, has_match: bool) -> ParsedResult:
    """Recompute detection_type and confidence using match info."""
    detection_type, confidence = _classify(parsed.extracted_fields, has_match=has_match)
    return ParsedResult(
        detection_type=detection_type,
        confidence_score=confidence,
        extracted_fields=parsed.extracted_fields,
        summary=_summarize(parsed.extracted_fields, detection_type),
    )


# ---------------------------------------------------------------------
# Backward-compat wrappers (for existing /email/inject + manual tests)
# ---------------------------------------------------------------------

def parse_text(subject: str, body: str, sender: Optional[str] = None) -> ParsedResult:
    """Convenience wrapper — when you have raw strings instead of an EU."""
    class _Stub:
        def __init__(self, s, b, sender):
            self.subject = s
            self.full_body_text = b
            self.body_excerpt = b[:500] if b else ""
            self.sender = sender
    return parse_email(_Stub(subject, body, sender))


# Legacy dict-shape parser used by older code paths. Returns the OLD shape.
def parse_email_legacy_dict(subject: str, body: str) -> Dict[str, Any]:
    parsed = parse_text(subject, body)
    f = parsed.extracted_fields
    out: Dict[str, Any] = {}
    if f.shipment_id:
        out["shp_id"] = f.shipment_id
    if f.container_numbers:
        out["container_numbers"] = f.container_numbers
    if f.booking_number:
        out["booking_number"] = f.booking_number
    if f.bl_number:
        out["bol_number"] = f.bl_number
    if f.invoice_number:
        out["invoice_number"] = f.invoice_number
    if f.po_number:
        out["po_number"] = f.po_number
    if f.eta_israel:
        out["eta_israel"] = f.eta_israel
    if f.etd:
        out["etd"] = f.etd
    out["delay_status"] = f.delay_detected
    out["looks_like_new_shipment"] = f.looks_like_new_shipment
    return out


def detected_to_jsonable(detected: Dict[str, Any]) -> Dict[str, Any]:
    """Helper used elsewhere — flattens dates to ISO strings."""
    return {
        k: (v.isoformat() if isinstance(v, (date, datetime)) else v)
        for k, v in detected.items()
    }
