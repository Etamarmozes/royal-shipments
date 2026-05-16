"""Pallet calculation service.

Given carton dimensions + cartons_total, computes how many pallets are needed
for two pallet types (Euro 120×80, Industrial 120×100) and recommends one.

Height constraint (UPDATED 2026-05-03):
- Max TOTAL height = 160 cm  (this is the warehouse stacking limit including pallet)
- Pallet itself takes ~15 cm by default (configurable per call)
- Available carton stack height = 160 − pallet_height
- max_layers = floor(available_carton_height / carton_height)

Other rules:
- Try both carton orientations on each pallet, take the better packing
- If carton dimensions are missing, fall back to ceil(cbm / 1.6) and note it

Pure functions — no DB access.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any

log = logging.getLogger("pallet")


# Pallet specs (cm)
EURO_LENGTH_CM = 120
EURO_WIDTH_CM = 80
INDUSTRIAL_LENGTH_CM = 120
INDUSTRIAL_WIDTH_CM = 100

# Total height limit for a loaded pallet (cartons + pallet itself)
MAX_TOTAL_HEIGHT_CM = 160

# Default pallet height (cm). Real wooden pallets are typically 14-15 cm.
DEFAULT_PALLET_HEIGHT_CM = 15

# CBM fallback: 1 standard pallet ≈ 1.6 CBM (heuristic from logistics norm)
CBM_PER_PALLET_FALLBACK = 1.6

# Tolerance for "auto" decision: if euro and industrial differ by ≤ this many
# pallets, prefer Euro (cheaper, more common in Israel).
AUTO_TIE_THRESHOLD = 1


# =====================================================================
# Public dataclasses
# =====================================================================

@dataclass
class PalletPackingResult:
    """Per-pallet-type packing detail."""
    pallet_type: str               # 'euro' or 'industrial'
    pallet_length_cm: int
    pallet_width_cm: int
    pallet_height_cm: float        # height the pallet itself adds
    available_carton_height_cm: float  # = max_total - pallet_height
    cartons_per_layer: int
    layers: int
    cartons_per_pallet: int
    cartons_stack_height_cm: Optional[float]  # actual cartons stack (= layers * carton_h)
    total_loaded_height_cm: Optional[float]   # = pallet_height + cartons_stack_height
    pallets_needed: Optional[int]  # None if cannot be calculated
    note: Optional[str] = None     # error / explanation


@dataclass
class PalletCalcResult:
    cartons_total: Optional[int]
    carton_length_cm: Optional[float]
    carton_width_cm: Optional[float]
    carton_height_cm: Optional[float]
    pallet_height_cm: float
    max_total_height_cm: float
    available_carton_height_cm: float
    method: str                    # 'dimensions' / 'cbm_fallback' / 'insufficient_data'
    euro: Optional[PalletPackingResult]
    industrial: Optional[PalletPackingResult]
    recommended_pallet_type: Optional[str]
    estimated_pallets_final: Optional[int]
    notes: str

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d


# =====================================================================
# Core math
# =====================================================================

def _cartons_per_layer(
    pallet_l: float, pallet_w: float, carton_l: float, carton_w: float,
) -> int:
    """How many cartons fit on a pallet layer, trying both orientations.

    Orientation A: carton_l along pallet_l, carton_w along pallet_w
    Orientation B: rotate 90° — carton_w along pallet_l, carton_l along pallet_w

    Doesn't try mixed-orientation packing (would require bin-packing); takes
    the best uniform-orientation result.
    """
    if carton_l <= 0 or carton_w <= 0:
        return 0
    a = math.floor(pallet_l / carton_l) * math.floor(pallet_w / carton_w)
    b = math.floor(pallet_l / carton_w) * math.floor(pallet_w / carton_l)
    return max(a, b)


def _max_layers(carton_h: float, available_height: float) -> int:
    """Layers that fit in the available carton height (above the pallet)."""
    if carton_h <= 0 or available_height <= 0:
        return 0
    return math.floor(available_height / carton_h)


def _calc_for_pallet(
    pallet_type: str, pallet_l: int, pallet_w: int,
    pallet_h: float, available_h: float,
    carton_l: float, carton_w: float, carton_h: float,
    cartons_total: int,
) -> PalletPackingResult:
    cpl = _cartons_per_layer(pallet_l, pallet_w, carton_l, carton_w)
    layers = _max_layers(carton_h, available_h)
    cpp = cpl * layers
    pallets: Optional[int] = None
    note: Optional[str] = None
    stack_h = layers * carton_h if layers and carton_h else None
    total_h = (pallet_h + stack_h) if stack_h is not None else None

    if cpl == 0:
        note = (
            f"קרטון {carton_l}×{carton_w} ס\"מ לא נכנס על משטח "
            f"{pallet_type} ({pallet_l}×{pallet_w})"
        )
    elif layers == 0:
        note = (
            f"גובה קרטון {carton_h} ס\"מ + משטח {pallet_h} ס\"מ עובר את מגבלת "
            f"{MAX_TOTAL_HEIGHT_CM} ס\"מ — לא ניתן לערום ולו שכבה אחת "
            f"(זמין לערימה: {available_h} ס\"מ)"
        )
    elif cpp > 0 and cartons_total > 0:
        pallets = math.ceil(cartons_total / cpp)

    return PalletPackingResult(
        pallet_type=pallet_type,
        pallet_length_cm=pallet_l,
        pallet_width_cm=pallet_w,
        pallet_height_cm=pallet_h,
        available_carton_height_cm=available_h,
        cartons_per_layer=cpl,
        layers=layers,
        cartons_per_pallet=cpp,
        cartons_stack_height_cm=stack_h,
        total_loaded_height_cm=total_h,
        pallets_needed=pallets,
        note=note,
    )


def _pick_recommended(
    preference: Optional[str],
    euro: Optional[PalletPackingResult],
    industrial: Optional[PalletPackingResult],
) -> Optional[str]:
    pref = (preference or "auto").lower()
    e_ok = euro and euro.pallets_needed is not None
    i_ok = industrial and industrial.pallets_needed is not None

    if pref == "euro" and e_ok:
        return "euro"
    if pref == "industrial" and i_ok:
        return "industrial"

    # auto / fallback
    if e_ok and i_ok:
        # If Euro doesn't fit at all, pick industrial; same vice-versa
        diff = euro.pallets_needed - industrial.pallets_needed
        if diff <= AUTO_TIE_THRESHOLD:
            return "euro"  # prefer Euro on tie or near-tie
        return "industrial"
    if e_ok:
        return "euro"
    if i_ok:
        return "industrial"
    return None


# =====================================================================
# Public API
# =====================================================================

def calculate(
    *,
    cartons_total: Optional[int],
    carton_length_cm: Optional[float],
    carton_width_cm: Optional[float],
    carton_height_cm: Optional[float],
    cbm: Optional[float] = None,
    pallet_type_preference: Optional[str] = "auto",
    pallet_height_cm: Optional[float] = None,
) -> PalletCalcResult:
    """Run the full pallet calc.

    Args:
        pallet_height_cm: how tall the pallet itself is (cm). Defaults to
            DEFAULT_PALLET_HEIGHT_CM (15). Subtracted from the 160 cm total.

    Returns a PalletCalcResult with euro / industrial / recommended /
    estimated_pallets_final / method.
    """
    pallet_h = pallet_height_cm if (pallet_height_cm and pallet_height_cm > 0) else DEFAULT_PALLET_HEIGHT_CM
    available_h = max(0.0, MAX_TOTAL_HEIGHT_CM - pallet_h)

    have_dims = (
        carton_length_cm and carton_length_cm > 0
        and carton_width_cm and carton_width_cm > 0
        and carton_height_cm and carton_height_cm > 0
    )
    have_count = cartons_total and cartons_total > 0

    # Fallback path: dimensions missing → use CBM
    if not (have_dims and have_count):
        if cbm and cbm > 0:
            pallets = math.ceil(cbm / CBM_PER_PALLET_FALLBACK)
            log.info("Pallet calc: CBM fallback, cbm=%.2f → %d pallets", cbm, pallets)
            return PalletCalcResult(
                cartons_total=cartons_total,
                carton_length_cm=carton_length_cm,
                carton_width_cm=carton_width_cm,
                carton_height_cm=carton_height_cm,
                pallet_height_cm=pallet_h,
                max_total_height_cm=MAX_TOTAL_HEIGHT_CM,
                available_carton_height_cm=available_h,
                method="cbm_fallback",
                euro=None,
                industrial=None,
                recommended_pallet_type=None,
                estimated_pallets_final=pallets,
                notes=(
                    f"חישוב לפי CBM (חסרות מידות קרטון או כמות). "
                    f"{cbm} CBM ÷ {CBM_PER_PALLET_FALLBACK} = {pallets} משטחים. "
                    "Calculated by CBM fallback."
                ),
            )
        log.info("Pallet calc: insufficient data — no dims, no count, no CBM")
        return PalletCalcResult(
            cartons_total=cartons_total,
            carton_length_cm=carton_length_cm,
            carton_width_cm=carton_width_cm,
            carton_height_cm=carton_height_cm,
            pallet_height_cm=pallet_h,
            max_total_height_cm=MAX_TOTAL_HEIGHT_CM,
            available_carton_height_cm=available_h,
            method="insufficient_data",
            euro=None,
            industrial=None,
            recommended_pallet_type=None,
            estimated_pallets_final=None,
            notes="חסרים נתונים: מידות קרטון או כמות או CBM.",
        )

    # Main path: full dimensions + count
    euro = _calc_for_pallet(
        "euro", EURO_LENGTH_CM, EURO_WIDTH_CM, pallet_h, available_h,
        carton_length_cm, carton_width_cm, carton_height_cm, cartons_total,
    )
    industrial = _calc_for_pallet(
        "industrial", INDUSTRIAL_LENGTH_CM, INDUSTRIAL_WIDTH_CM, pallet_h, available_h,
        carton_length_cm, carton_width_cm, carton_height_cm, cartons_total,
    )

    recommended = _pick_recommended(pallet_type_preference, euro, industrial)
    final_pallets = None
    if recommended == "euro":
        final_pallets = euro.pallets_needed
    elif recommended == "industrial":
        final_pallets = industrial.pallets_needed

    # Build note
    notes_parts = []
    notes_parts.append(
        f"קרטון {carton_length_cm}×{carton_width_cm}×{carton_height_cm} ס\"מ × {cartons_total} יח' "
        f"(מגבלה {MAX_TOTAL_HEIGHT_CM} ס\"מ כולל משטח {pallet_h} ס\"מ → זמין לקרטונים: {available_h} ס\"מ)"
    )
    if euro.pallets_needed is not None:
        notes_parts.append(
            f"Euro 120×80: {euro.cartons_per_layer}/שכבה × {euro.layers} שכבות = "
            f"{euro.cartons_per_pallet}/משטח (גובה כולל {euro.total_loaded_height_cm:.0f} ס\"מ) → "
            f"{euro.pallets_needed} משטחים"
        )
    elif euro.note:
        notes_parts.append(f"Euro: {euro.note}")
    if industrial.pallets_needed is not None:
        notes_parts.append(
            f"Industrial 120×100: {industrial.cartons_per_layer}/שכבה × {industrial.layers} שכבות = "
            f"{industrial.cartons_per_pallet}/משטח (גובה כולל {industrial.total_loaded_height_cm:.0f} ס\"מ) → "
            f"{industrial.pallets_needed} משטחים"
        )
    elif industrial.note:
        notes_parts.append(f"Industrial: {industrial.note}")
    if recommended:
        notes_parts.append(f"המלצה: {recommended} ({final_pallets} משטחים)")

    log.info(
        "Pallet calc: cartons=%d dims=%sx%sx%s pallet_h=%s avail=%s pref=%s euro=%s ind=%s → rec=%s final=%s",
        cartons_total, carton_length_cm, carton_width_cm, carton_height_cm,
        pallet_h, available_h, pallet_type_preference,
        euro.pallets_needed, industrial.pallets_needed,
        recommended, final_pallets,
    )

    return PalletCalcResult(
        cartons_total=cartons_total,
        carton_length_cm=carton_length_cm,
        carton_width_cm=carton_width_cm,
        carton_height_cm=carton_height_cm,
        pallet_height_cm=pallet_h,
        max_total_height_cm=MAX_TOTAL_HEIGHT_CM,
        available_carton_height_cm=available_h,
        method="dimensions",
        euro=euro,
        industrial=industrial,
        recommended_pallet_type=recommended,
        estimated_pallets_final=final_pallets,
        notes=" • ".join(notes_parts),
    )


def apply_to_container(container, pallet_type_preference_override: Optional[str] = None) -> PalletCalcResult:
    """Calculate pallets for a Container ORM row and apply results to its
    estimated_* / recommended_* fields. Caller commits the session."""
    pref = pallet_type_preference_override or container.pallet_type_preference or "auto"
    result = calculate(
        cartons_total=container.boxes_total,
        carton_length_cm=container.carton_length_cm,
        carton_width_cm=container.carton_width_cm,
        carton_height_cm=container.carton_height_cm,
        cbm=container.cbm,
        pallet_type_preference=pref,
    )
    container.estimated_pallets_euro = result.euro.pallets_needed if result.euro else None
    container.estimated_pallets_industrial = (
        result.industrial.pallets_needed if result.industrial else None
    )
    container.recommended_pallet_type = result.recommended_pallet_type
    container.estimated_pallets_final = result.estimated_pallets_final
    container.pallet_calc_notes = result.notes
    return result
