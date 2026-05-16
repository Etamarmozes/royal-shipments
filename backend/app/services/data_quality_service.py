"""Data-quality scoring for shipments and containers.

The score is intentionally simple — three buckets per entity:

  - **complete**:        no critical or minor issues
  - **missing_minor**:   only minor data missing (notes, image, tags)
  - **missing_critical**: at least one critical field missing

Critical fields are those that block planning or warehouse receiving.
Minor fields are ergonomic / nice-to-have.
"""
from __future__ import annotations

from typing import List, Dict, Any
from ..models import Shipment, Container


# ---- Field definitions ----

SHIPMENT_CRITICAL = [
    ("supplier",          "ספק"),
    ("category",          "קטגוריה"),
    ("eta_israel",        "ETA לארץ"),
    ("goods_description", "תיאור סחורה"),
]
SHIPMENT_MINOR = [
    ("notes",              "הערות"),
    ("product_image_path", "תמונת מוצר"),
    ("po_number",          "PO"),
    ("invoice_number",     "Invoice"),
    ("booking_number",     "Booking"),
    ("bol_number",         "BL/BOL"),
]

CONTAINER_CRITICAL = [
    ("container_number", "מספר מכולה"),
    ("boxes_total",      "כמות קרטונים"),
    ("cbm",              "CBM"),
    ("eta_israel",       "ETA"),
]
CONTAINER_MINOR = [
    ("carton_length_cm", "אורך קרטון"),
    ("carton_width_cm",  "רוחב קרטון"),
    ("carton_height_cm", "גובה קרטון"),
    ("gross_weight_kg",  "משקל ברוטו"),
    ("container_type",   "סוג מכולה"),
    ("notes",            "הערות"),
]


def _is_blank(v) -> bool:
    if v is None:
        return True
    if isinstance(v, str) and not v.strip():
        return True
    if isinstance(v, (int, float)) and v == 0:
        return True
    return False


def _check(obj, fields):
    """Returns list of (field, label) tuples for missing fields."""
    missing = []
    for f, label in fields:
        if _is_blank(getattr(obj, f, None)):
            missing.append({"field": f, "label": label})
    return missing


def shipment_quality(s: Shipment) -> Dict[str, Any]:
    crit = _check(s, SHIPMENT_CRITICAL)
    minor = _check(s, SHIPMENT_MINOR)
    if crit:
        score = "missing_critical"
    elif minor:
        score = "missing_minor"
    else:
        score = "complete"
    return {
        "entity_type": "shipment",
        "entity_id": s.id,
        "score": score,
        "missing_critical": crit,
        "missing_minor": minor,
        "missing_count": len(crit) + len(minor),
    }


def container_quality(c: Container) -> Dict[str, Any]:
    crit = _check(c, CONTAINER_CRITICAL)
    # Carton dimensions: only one trio counts as critical when ALL three blank
    # (otherwise the pallet calc has its CBM fallback) — handled here as minor.
    minor = _check(c, CONTAINER_MINOR)

    # Effective category: take container override or fall back to shipment
    eff_cat = c.category or (c.shipment.category if c.shipment else None)
    if _is_blank(eff_cat):
        crit.append({"field": "category", "label": "קטגוריה"})

    if crit:
        score = "missing_critical"
    elif minor:
        score = "missing_minor"
    else:
        score = "complete"
    return {
        "entity_type": "container",
        "entity_id": c.id,
        "score": score,
        "missing_critical": crit,
        "missing_minor": minor,
        "missing_count": len(crit) + len(minor),
    }
