"""Document Intelligence — classification + email-noise filtering.

Pure functions. NEVER mutates `email_attachments.linked_shipment_id` or
the file on disk. The classifier returns a label + confidence + reason,
and the caller decides whether to persist.

CLASSIFICATION VOCABULARY:
    shipment_document, commercial_invoice, packing_list,
    bill_of_lading, house_bill_of_lading, master_bill_of_lading,
    purchase_order, customs_document, delivery_note, certificate,
    product_image, email_noise, unknown_needs_review
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..config import UPLOADS_DIR
from ..models import EmailAttachment, EmailUpdate

# Where files live on disk
DOCS_DIR = UPLOADS_DIR / "documents"


# =====================================================================
# Email-noise heuristics
# =====================================================================

# Filename substrings that strongly suggest noise
_NOISE_FILENAME_PATTERNS = [
    "image001", "image002", "image003", "image004", "image005",
    "image00", "image0", "image_001",
    "logo", "signature", "footer", "banner",
    "icon", "social", "facebook", "instagram", "linkedin", "whatsapp",
    "twitter", "tracking-pixel", "tracking_pixel",
    "spacer", "divider",
]

# Brand/company logos commonly in email signatures
_BRAND_LOGO_PATTERNS = [
    "royallinen", "royal_linen", "royal linen",
    "nautica", "puma", "keds", "polder", "lifetime",
    "brooks brothers", "brooksbrothers",
]

# Image extensions
_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".svg", ".ico"}

# Document extensions (high-priority valid extensions)
_DOC_EXTS = {".pdf", ".xlsx", ".xls", ".xlsm", ".docx", ".doc", ".csv"}

# Filenames that should NEVER be classified as documents (well-known noise)
_NOISE_EXACT_FILENAMES = {
    "att00001.jpg", "att00002.jpg", "att00003.jpg",
    "att00001.htm",
}

# Threshold: images smaller than this on disk are treated as noise candidates
SMALL_IMAGE_BYTES = 30 * 1024     # 30 KB
TINY_IMAGE_BYTES = 5 * 1024       # 5 KB → almost certainly noise
LARGE_DOC_BYTES = 50 * 1024       # ≥ this size with non-noise filename → likely real


# =====================================================================
# Document type keyword tables (English + Hebrew)
# =====================================================================

# Each entry: (regex, classification, base_confidence, reason_template)
# Order matters — first match wins.
_DOC_TYPE_RULES: List[Tuple[re.Pattern, str, float, str]] = [
    # House BL — must come before generic BL
    (re.compile(r"\bhbl\b|house[\s_\-]?bill[\s_\-]?of[\s_\-]?lading", re.IGNORECASE),
     "house_bill_of_lading", 0.92, "filename mentions HBL"),
    (re.compile(r"\bmbl\b|master[\s_\-]?bill[\s_\-]?of[\s_\-]?lading", re.IGNORECASE),
     "master_bill_of_lading", 0.92, "filename mentions MBL"),
    (re.compile(r"\bbol\b", re.IGNORECASE),
     "bill_of_lading", 0.88, "filename mentions BOL"),
    (re.compile(r"bill[\s_\-]?of[\s_\-]?lading", re.IGNORECASE),
     "bill_of_lading", 0.92, "filename mentions Bill of Lading"),
    (re.compile(r"\bbl\b", re.IGNORECASE),
     "bill_of_lading", 0.85, "filename mentions BL"),
    (re.compile(r"שטר[\s_\-]?מטען", re.IGNORECASE),
     "bill_of_lading", 0.92, "filename mentions שטר מטען"),

    # Commercial invoice
    (re.compile(r"commercial[\s_\-]?invoice", re.IGNORECASE),
     "commercial_invoice", 0.95, "filename mentions Commercial Invoice"),
    (re.compile(r"\binvoice\b|\binv\b|\binv[\-_\s]?\d", re.IGNORECASE),
     "commercial_invoice", 0.85, "filename mentions Invoice/INV"),
    (re.compile(r"חשבונית", re.IGNORECASE),
     "commercial_invoice", 0.92, "filename mentions חשבונית"),

    # Packing List
    (re.compile(r"packing[\s_\-]?list|packinglist", re.IGNORECASE),
     "packing_list", 0.95, "filename mentions Packing List"),
    (re.compile(r"\bpl\b|p[/_\-]l\b", re.IGNORECASE),
     "packing_list", 0.80, "filename mentions PL / P/L"),
    (re.compile(r"רשימת[\s_\-]?אריזה", re.IGNORECASE),
     "packing_list", 0.95, "filename mentions רשימת אריזה"),
    (re.compile(r"אריזה", re.IGNORECASE),
     "packing_list", 0.75, "filename mentions אריזה"),

    # Booking → BL precursor
    (re.compile(r"booking[\s_\-]?confirmation|booking[\s_\-]?conf",
                re.IGNORECASE),
     "bill_of_lading", 0.70, "booking confirmation"),
    (re.compile(r"\bbooking\b", re.IGNORECASE),
     "bill_of_lading", 0.65, "booking"),

    # Customs
    (re.compile(r"customs|מכס", re.IGNORECASE),
     "customs_document", 0.90, "filename mentions customs / מכס"),

    # Purchase order
    (re.compile(r"purchase[\s_\-]?order|^po[\s_\-]?\d|\bpo\b", re.IGNORECASE),
     "purchase_order", 0.80, "filename mentions PO"),
    (re.compile(r"הזמנה", re.IGNORECASE),
     "purchase_order", 0.75, "filename mentions הזמנה"),

    # Certificate
    (re.compile(r"certificate|cert\b|תעודה", re.IGNORECASE),
     "certificate", 0.85, "filename mentions certificate"),

    # Delivery
    (re.compile(r"delivery[\s_\-]?note|delivery[\s_\-]?order|\bdo\b|אספקה",
                re.IGNORECASE),
     "delivery_note", 0.80, "filename mentions delivery note"),
]


# =====================================================================
# Helpers
# =====================================================================

def _filename_low(att: EmailAttachment) -> str:
    return (att.filename or "").lower()


def _ext(att: EmailAttachment) -> str:
    return Path(att.filename or "").suffix.lower()


def _file_size(att: EmailAttachment) -> Optional[int]:
    """Best-effort file size (bytes). Falls back to attachment.file_size
    if the on-disk lookup fails."""
    if att.file_path:
        try:
            p = DOCS_DIR / Path(att.file_path).name
            if p.exists():
                return p.stat().st_size
        except Exception:
            pass
    return att.file_size


def _is_image_ext(ext: str) -> bool:
    return ext in _IMAGE_EXTS


def _is_inline(att: EmailAttachment) -> bool:
    """Heuristic for inline attachment (Content-Id / image001 pattern).
    The Gmail sync stores `gmail_attachment_id` for true attachments; inline
    images are also stored, but their filenames typically follow image00X.
    `is_inline` column stores the explicit flag if known."""
    if att.is_inline:
        return True
    # Treat any image00X as inline
    name = _filename_low(att)
    if name.startswith("image00") and _is_image_ext(_ext(att)):
        return True
    return False


def _filename_has_brand_logo(name: str) -> bool:
    return any(b in name for b in _BRAND_LOGO_PATTERNS)


def _filename_has_noise_pattern(name: str) -> bool:
    return any(p in name for p in _NOISE_FILENAME_PATTERNS)


# =====================================================================
# Classifier
# =====================================================================

def classify(att: EmailAttachment, eu: Optional[EmailUpdate] = None) -> Dict[str, Any]:
    """Classify ONE attachment. Pure — no DB writes.

    Returns:
      {
        "classification": str,
        "confidence": float (0..1),
        "reason": str,
        "is_email_noise": bool,
      }

    Decision order:
      1. Manual override → keep what the user picked
      2. Inline + small image → email_noise
      3. Drive link → shipment_document (we trust links)
      4. Filename matches known noise pattern + image ext → email_noise
      5. Filename has brand logo + image ext → email_noise
      6. Image with very small file size → email_noise
      7. Filename matches doc-type keyword → that type
      8. PDF/Excel/Word with no other clue → shipment_document (low conf)
      9. Large image without noise markers → product_image
     10. Otherwise → unknown_needs_review
    """
    # 1. Manual override
    if att.manually_classified_by and att.classification:
        return {
            "classification": att.classification,
            "confidence": 1.0,
            "reason": f"manually classified by {att.manually_classified_by}",
            "is_email_noise": att.classification == "email_noise",
        }

    name = _filename_low(att)
    ext = _ext(att)
    size = _file_size(att) or 0
    inline = _is_inline(att)

    # 3. Drive link (no file, just a URL) — trust the link as a doc
    if att.source_url and not att.file_path:
        return {
            "classification": "shipment_document",
            "confidence": 0.7,
            "reason": "Drive link — assumed shipment document",
            "is_email_noise": False,
        }

    # 2 + 4 + 5 + 6. Email noise checks for images
    if _is_image_ext(ext):
        # Exact-name noise
        bare = Path(name).name
        if bare in _NOISE_EXACT_FILENAMES:
            return {
                "classification": "email_noise",
                "confidence": 0.95,
                "reason": f"filename '{bare}' is a known noise pattern",
                "is_email_noise": True,
            }
        # image00X-style → inline image
        if name.startswith("image00") or inline:
            # Even moderately large image00X are usually email decorations
            return {
                "classification": "email_noise",
                "confidence": 0.92 if size < SMALL_IMAGE_BYTES else 0.75,
                "reason": (
                    f"inline / image00X pattern (size {size}B)"
                    if size < SMALL_IMAGE_BYTES
                    else f"inline / image00X pattern (size {size}B)"
                ),
                "is_email_noise": True,
            }
        # Logo / signature filename
        if _filename_has_noise_pattern(name) or _filename_has_brand_logo(name):
            return {
                "classification": "email_noise",
                "confidence": 0.92,
                "reason": (
                    f"filename suggests logo/signature/social ({Path(name).name})"
                ),
                "is_email_noise": True,
            }
        # Very small image
        if 0 < size < TINY_IMAGE_BYTES:
            return {
                "classification": "email_noise",
                "confidence": 0.90,
                "reason": f"tiny image ({size}B < {TINY_IMAGE_BYTES}B)",
                "is_email_noise": True,
            }
        if 0 < size < SMALL_IMAGE_BYTES:
            return {
                "classification": "email_noise",
                "confidence": 0.65,
                "reason": f"small image ({size}B < {SMALL_IMAGE_BYTES}B)",
                "is_email_noise": True,
            }
        # Bigger image → likely a real product photo
        if size >= LARGE_DOC_BYTES:
            return {
                "classification": "product_image",
                "confidence": 0.55,
                "reason": f"image, {size}B — likely product photo",
                "is_email_noise": False,
            }
        return {
            "classification": "unknown_needs_review",
            "confidence": 0.4,
            "reason": f"image of unclear purpose ({size}B)",
            "is_email_noise": False,
        }

    # 7a. Filename keyword matching FIRST — filename is the most reliable
    # signal. We check filename in isolation so that an email-body mention
    # of "Invoice" can't override a file actually named "PL - …".
    fname_only = att.filename or ""
    for rx, label, base_conf, reason_template in _DOC_TYPE_RULES:
        if rx.search(fname_only):
            return {
                "classification": label,
                "confidence": base_conf,
                "reason": f"{reason_template} (filename match)",
                "is_email_noise": False,
            }

    # 7b. Fallback — subject + body. Lower confidence since the parent email
    # might be discussing a doc that isn't this attachment.
    subject_body = " ".join([
        eu.subject if eu else "",
        eu.body_excerpt if eu else "",
    ])
    for rx, label, base_conf, reason_template in _DOC_TYPE_RULES:
        if rx.search(subject_body):
            return {
                "classification": label,
                "confidence": max(0.50, base_conf - 0.15),   # demote
                "reason": f"{reason_template} (subject/body, not filename)",
                "is_email_noise": False,
            }

    # 8. PDF / Excel / Word with no other signal → generic shipment document
    if ext in _DOC_EXTS:
        return {
            "classification": "shipment_document",
            "confidence": 0.55,
            "reason": f"document file ({ext}) without explicit type marker",
            "is_email_noise": False,
        }

    # 10. Otherwise — unknown
    return {
        "classification": "unknown_needs_review",
        "confidence": 0.3,
        "reason": f"unclassified extension {ext or '(none)'}",
        "is_email_noise": False,
    }


# =====================================================================
# Bulk operations
# =====================================================================

def classify_and_save(att: EmailAttachment, eu: Optional[EmailUpdate],
                      *, persist: bool = True) -> Dict[str, Any]:
    """Classify + (optionally) write the result onto the attachment row.
    Caller does db.commit()."""
    result = classify(att, eu)
    if persist:
        # Don't overwrite a manual classification
        if not att.manually_classified_by:
            att.classification = result["classification"]
            att.classification_confidence = result["confidence"]
            att.classification_reason = result["reason"]
            att.is_email_noise = result["is_email_noise"]
            att.classified_at = datetime.utcnow()
        else:
            # Keep manual values, but update the auto-suggestion as a hint
            pass
    return result


# =====================================================================
# Required-doc-type satisfiers
# =====================================================================

# Maps a "required type" to the set of classifications that satisfy it
TYPE_SATISFIERS: Dict[str, set[str]] = {
    "invoice": {"commercial_invoice"},
    "packing_list": {"packing_list"},
    "bl": {"bill_of_lading", "house_bill_of_lading", "master_bill_of_lading"},
}


def classification_satisfies(required: str, classification: Optional[str]) -> bool:
    if not classification:
        return False
    return classification in TYPE_SATISFIERS.get(required, set())
