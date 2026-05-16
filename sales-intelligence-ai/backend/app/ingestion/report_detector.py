"""
Detect what kind of Comax report a file is.

Returns one of:
  - "sales"
  - "inventory"
  - "items_master"
  - "stores_master"
  - "unknown"
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .column_normalizer import map_headers


@dataclass
class DetectionResult:
    report_type: str
    confidence: str  # "high" | "medium" | "low" | "none"
    reasons: list[str]


_FILENAME_HINTS = {
    "sales": ["sales", "מכר", "מכירות", "מכירה"],
    "inventory": ["inventory", "מלאי", "stock"],
    "items_master": ["items master", "item master", "פריטים", "קטלוג"],
    "stores_master": ["stores", "סניפים", "store list"],
}


def _filename_hint(filename: str) -> tuple[str | None, str]:
    name = filename.lower()
    for rtype, words in _FILENAME_HINTS.items():
        for w in words:
            if w in name:
                return rtype, f"filename contains '{w}'"
    return None, ""


def _column_signature(canonical_fields: set[str]) -> tuple[str | None, str]:
    """Decide based on which canonical columns are present."""
    has = canonical_fields.__contains__

    if has("date") and has("store_code") and (has("quantity") or has("net_sales") or has("gross_sales")):
        return "sales", "has date+store+(qty/sales)"

    if (has("inventory_quantity") or has("available_quantity")) and (has("store_code") or has("snapshot_date")):
        return "inventory", "has inventory_quantity"

    if has("item_code") and has("item_name") and (has("brand") or has("category") or has("selling_price")):
        if not has("date") and not has("inventory_quantity"):
            return "items_master", "has item_code+item_name+brand/category, no date/inv"

    if has("store_code") and has("store_name") and not has("item_code") and not has("date"):
        return "stores_master", "stores list signature"

    return None, "no clear column signature"


def detect_report_type(filename: str, headers: Iterable[str]) -> DetectionResult:
    headers_list = [h for h in headers if h is not None]
    _, unmapped = map_headers(headers_list)
    canonical = set(map_headers(headers_list)[0].values())

    name_guess, name_reason = _filename_hint(Path(filename).name)
    sig_guess, sig_reason = _column_signature(canonical)

    reasons: list[str] = []
    if name_reason:
        reasons.append(name_reason)
    if sig_reason:
        reasons.append(sig_reason)

    if name_guess and sig_guess and name_guess == sig_guess:
        return DetectionResult(name_guess, "high", reasons)
    if sig_guess:
        return DetectionResult(sig_guess, "medium" if name_guess is None or name_guess == sig_guess else "medium", reasons)
    if name_guess:
        return DetectionResult(name_guess, "low", reasons + ["filename only"])

    return DetectionResult("unknown", "none", reasons + [f"unmapped headers: {unmapped[:6]}"])
