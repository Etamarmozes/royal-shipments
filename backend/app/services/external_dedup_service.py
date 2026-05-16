"""Duplicate / similarity detection for incoming Excel preview rows.

Pure functions — read-only against the live shipments table. Run during
the /import/excel/preview step. The result is attached to each preview
row so the user sees warnings BEFORE typing APPLY.

Match levels:
  exact_duplicate           90..100  red badge   default action: skip
  strong_possible_match     70..89   orange      default action: skip
  soft_possible_match       40..69   yellow      default action: create (with warning)
  no_match                   0..39   no badge    default action: create

Scoring (additive; capped at 100):
  shipment_reference / external_file / external_job exact match  +100
  real container_number exact match                              +100
  HBL or MBL exact match                                          +95
  PO exact match                                                  +90
  marks exact match                                               +80
  same supplier (normalised)                                      +30
  exact ETA match                                                 +25
  ETA within 7 days                                               +15
  same origin port                                                +10
  same destination port                                           +10
  same category / brand / inferred_brand                          +20
  product description text similarity (jaccard >= 0.5)            +20
  product description partial overlap (jaccard 0.2-0.5)           +10
  same carrier or vessel                                          +10

Reasons are returned as a list of short Hebrew strings so the UI can
show them inline.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

from sqlalchemy.orm import Session, joinedload

from ..models import Container, Shipment


# =====================================================================
# Normalisation
# =====================================================================

_COMPANY_NOISE = re.compile(
    r"\b(ltd|limited|inc|inc\.|co\.?|corp|corporation|llc|gmbh|"
    r"daily|daily \w+|kenries daily|trading|products?|industries|"
    r"company|companies)\b",
    re.IGNORECASE,
)


def _norm_supplier(s: Optional[str]) -> str:
    if not s:
        return ""
    out = s.strip().lower()
    # Treat "/" as a separator — many of our suppliers are
    # "X / Y" so just keep the LHS for matching
    if "/" in out:
        out = out.split("/", 1)[0].strip()
    out = _COMPANY_NOISE.sub(" ", out)
    out = re.sub(r"[^\w\s֐-׿]", " ", out)  # keep Latin + Hebrew
    out = re.sub(r"\s+", " ", out).strip()
    return out


def _norm_id(v: Optional[str]) -> str:
    """Normalise an identifier for exact comparison."""
    if v is None:
        return ""
    s = str(v).strip().upper()
    # Strip non-alphanumerics so "MEDU WP 851167" == "MEDUWP851167"
    return re.sub(r"[^A-Z0-9]", "", s)


def _to_date(v) -> Optional[date]:
    if v in (None, ""):
        return None
    if isinstance(v, date) and not isinstance(v, datetime):
        return v
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, str):
        try:
            return date.fromisoformat(v.strip()[:10])
        except Exception:
            return None
    return None


_TOKEN_SPLIT = re.compile(r"[\s,/\-_.]+")


def _tokens(text: Optional[str]) -> set[str]:
    if not text:
        return set()
    parts = _TOKEN_SPLIT.split(text.lower())
    # Drop very short tokens (<3) and pure digits — they're too generic
    return {p for p in parts if len(p) >= 3 and not p.isdigit()}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = a & b
    union = a | b
    return len(inter) / max(1, len(union))


# =====================================================================
# Per-pair scoring
# =====================================================================

def score_pair(row: Dict[str, Any], shipment: Shipment) -> Tuple[int, List[str]]:
    """Score how likely `row` (incoming) matches `shipment` (existing).
    Returns (score, reasons[]). Score is capped at 100.
    """
    score = 0
    reasons: List[str] = []

    # --- Hard identifiers (any of these → exact-duplicate territory) ---
    incoming_ref = _norm_id(row.get("shipment_reference"))
    if incoming_ref:
        if incoming_ref == _norm_id(shipment.shp_id):
            score += 100
            reasons.append(f"shipment_reference זהה ל-{shipment.shp_id}")
        if incoming_ref == _norm_id(shipment.external_file_number):
            score += 100
            reasons.append(f"external_file_number זהה ({shipment.external_file_number})")
        if incoming_ref == _norm_id(shipment.external_job_number):
            score += 100
            reasons.append(f"external_job_number זהה ({shipment.external_job_number})")

    incoming_ext_file = _norm_id(row.get("external_file_number"))
    if incoming_ext_file and incoming_ext_file == _norm_id(shipment.external_file_number):
        score += 100
        reasons.append(f"ICL file no זהה: {shipment.external_file_number}")

    incoming_ext_job = _norm_id(row.get("external_job_number"))
    if incoming_ext_job and incoming_ext_job == _norm_id(shipment.external_job_number):
        score += 100
        reasons.append(f"JOB number זהה: {shipment.external_job_number}")

    # BL — match incoming HBL or MBL against shipment's HBL/MBL or legacy bol_number
    incoming_bls = {_norm_id(row.get(k))
                    for k in ("house_bill_of_lading_number",
                               "master_bill_of_lading_number",
                               "bill_of_lading_number")
                    if row.get(k)}
    incoming_bls.discard("")
    existing_bls = {_norm_id(shipment.bol_number),
                    _norm_id(shipment.house_bill_of_lading_number),
                    _norm_id(shipment.master_bill_of_lading_number)}
    existing_bls.discard("")
    bl_overlap = incoming_bls & existing_bls
    if bl_overlap:
        score += 95
        reasons.append(f"BL/BOL זהה ({list(bl_overlap)[0]})")

    # PO
    incoming_po_str = (row.get("purchase_order_number") or "")
    incoming_po = _norm_id(incoming_po_str)
    if incoming_po:
        existing_po = _norm_id(shipment.po_number)
        if existing_po:
            if incoming_po == existing_po:
                score += 90
                reasons.append(f"PO זהה ({shipment.po_number})")
            elif (existing_po in incoming_po or incoming_po in existing_po) \
                    and len(existing_po) >= 6:
                score += 40   # partial PO match
                reasons.append(f"PO חופף חלקית ({shipment.po_number})")

    # Real container number — only count if incoming has a REAL (non-placeholder)
    # number. The ICL/Eli imports don't supply real numbers, so this branch
    # only triggers for our Royal Linen template format.
    incoming_cn = _norm_id(row.get("container_number"))
    if incoming_cn:
        # Look up across ALL containers of this shipment
        for c in (shipment.containers or []):
            if not c.container_number:
                continue
            if c.placeholder_container or c.actual_container_number_missing:
                continue   # never match against placeholders
            if _norm_id(c.container_number) == incoming_cn:
                score += 100
                reasons.append(f"מכולה זהה: {c.container_number}")
                break

    # Marks (Eli Line)
    incoming_marks = _norm_id(row.get("marks"))
    if incoming_marks and incoming_marks == _norm_id(shipment.marks):
        score += 80
        reasons.append(f"marks זהה: {shipment.marks}")

    # Customs file number
    incoming_cf = _norm_id(row.get("customs_file_number"))
    if incoming_cf and incoming_cf == _norm_id(shipment.customs_file_number):
        score += 80
        reasons.append(f"customs file זהה: {shipment.customs_file_number}")

    # Sho list
    incoming_sho = _norm_id(row.get("sho_list"))
    if incoming_sho and incoming_sho == _norm_id(shipment.sho_list):
        score += 70
        reasons.append(f"Sho list זהה: {shipment.sho_list}")

    # Invoice
    incoming_inv = _norm_id(row.get("invoice_number"))
    if incoming_inv and incoming_inv == _norm_id(shipment.invoice_number):
        score += 90
        reasons.append(f"Invoice זהה: {shipment.invoice_number}")

    # --- Soft signals ---
    sup_in = _norm_supplier(row.get("supplier_name"))
    sup_db = _norm_supplier(shipment.supplier)
    same_supplier = bool(sup_in and sup_db and (sup_in == sup_db
                                                  or sup_in in sup_db
                                                  or sup_db in sup_in))
    if same_supplier:
        score += 30
        reasons.append("ספק זהה")

    # ETA — try eta_port first, else eta_warehouse, else etd
    eta_in = _to_date(row.get("eta_port") or row.get("eta_warehouse"))
    eta_db = shipment.eta_port or shipment.eta_warehouse
    if eta_in and eta_db:
        delta = abs((eta_in - eta_db).days)
        if delta == 0:
            score += 25
            reasons.append(f"ETA זהה ({eta_db.isoformat()})")
        elif delta <= 7:
            score += 15
            reasons.append(f"ETA קרוב (פער {delta} ימים)")

    # Origin / destination ports
    origin_in = (row.get("origin_port") or "").strip().lower()
    origin_db = (shipment.origin_port or "").strip().lower()
    if origin_in and origin_in == origin_db:
        score += 10
        reasons.append(f"מקור זהה: {shipment.origin_port}")

    dest_in = (row.get("destination_port") or "").strip().lower()
    dest_db = (shipment.destination_port or "").strip().lower()
    if dest_in and dest_in == dest_db:
        score += 10
        reasons.append(f"יעד זהה: {shipment.destination_port}")

    # Category / brand
    cat_in = (row.get("category") or row.get("inferred_category") or "").strip().lower()
    cat_db = (shipment.category or shipment.inferred_category or "").strip().lower()
    if cat_in and cat_in == cat_db:
        score += 20
        reasons.append(f"קטגוריה זהה: {shipment.category or shipment.inferred_category}")

    brand_in = (row.get("inferred_brand") or row.get("brand") or "").strip().lower()
    brand_db = (shipment.inferred_brand or "").strip().lower()
    if brand_in and brand_in == brand_db:
        score += 20
        reasons.append(f"מותג זהה: {shipment.inferred_brand}")

    # Product description similarity
    desc_in = row.get("product_description") or row.get("product_description_raw") or ""
    desc_db = shipment.goods_description or shipment.product_description_raw or ""
    if desc_in and desc_db:
        j = _jaccard(_tokens(desc_in), _tokens(desc_db))
        if j >= 0.5:
            score += 20
            reasons.append(f"תיאור מוצר דומה (jaccard {j:.2f})")
        elif j >= 0.2:
            score += 10
            reasons.append(f"תיאור מוצר חופף חלקית (jaccard {j:.2f})")

    # Carrier / vessel
    carrier_in = (row.get("carrier") or row.get("shipping_company") or "").strip().lower()
    carrier_db = (shipment.carrier or shipment.shipping_channel or "").strip().lower()
    if carrier_in and carrier_in == carrier_db:
        score += 10
        reasons.append(f"מוביל זהה: {shipment.carrier or shipment.shipping_channel}")

    vessel_in = (row.get("vessel_name") or "").strip().lower()
    vessel_db = (shipment.vessel_name or "").strip().lower()
    if vessel_in and vessel_in == vessel_db:
        score += 10
        reasons.append(f"אונייה זהה: {shipment.vessel_name}")

    return min(100, score), reasons


# =====================================================================
# Match-level classification
# =====================================================================

def classify(score: int) -> str:
    if score >= 90:
        return "exact_duplicate"
    if score >= 70:
        return "strong_possible_match"
    if score >= 40:
        return "soft_possible_match"
    return "no_match"


# =====================================================================
# Main entry point
# =====================================================================

def find_matches(db: Session, row: Dict[str, Any]) -> Dict[str, Any]:
    """Score `row` against every active shipment. Return the verdict +
    top 3 possible matches.

    Active = `archived = False`. Archived shipments are ignored — they're
    not duplicates of incoming live data.
    """
    shipments = (
        db.query(Shipment)
        .options(joinedload(Shipment.containers))
        .filter(Shipment.archived == False)   # noqa: E712
        .all()
    )

    scored: List[Dict[str, Any]] = []
    for s in shipments:
        score, reasons = score_pair(row, s)
        if score <= 0:
            continue
        scored.append({
            "shipment_id": s.id,
            "shipment_reference": s.shp_id,
            "supplier_name": s.supplier,
            "category": s.category,
            "eta_port": s.eta_port.isoformat() if s.eta_port else None,
            "eta_warehouse": s.eta_warehouse.isoformat() if s.eta_warehouse else None,
            "status": s.stage_status,
            "match_score": score,
            "match_reasons": reasons,
        })

    scored.sort(key=lambda x: -x["match_score"])
    top = scored[:3]

    if top:
        best = top[0]
        match_score = best["match_score"]
        match_level = classify(match_score)
        match_reasons = best["match_reasons"]
        matched_shipment_id = best["shipment_id"]
    else:
        match_score = 0
        match_level = "no_match"
        match_reasons = []
        matched_shipment_id = None

    return {
        "match_level": match_level,
        "match_score": match_score,
        "match_reasons": match_reasons,
        "matched_shipment_id": matched_shipment_id,
        "matched_shipment_reference":
            top[0]["shipment_reference"] if top else None,
        "matched_shipment_supplier":
            top[0]["supplier_name"] if top else None,
        "possible_matches": top,
    }


# =====================================================================
# Default action helper
# =====================================================================

def default_action_for(match_level: str, needs_review: bool) -> str:
    """Compute the safe default `_action` for a preview row.

    Per spec:
      - needs_review trumps everything → skip
      - exact_duplicate → skip (user can flip to update)
      - strong_possible_match → skip
      - soft_possible_match → create (warned)
      - no_match → create
    """
    if needs_review:
        return "skip"
    if match_level in ("exact_duplicate", "strong_possible_match"):
        return "skip"
    return "create"


# Match levels that require an explicit override before "create" is allowed
UNSAFE_CREATE_LEVELS = {"exact_duplicate", "strong_possible_match"}
