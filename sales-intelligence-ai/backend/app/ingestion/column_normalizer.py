"""
Bilingual column header → canonical field mapping.

Lookup is case-insensitive, whitespace-stripped, and ignores Hebrew niqqud.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Dict, Iterable

# canonical field name → list of accepted source headers (Hebrew + English)
HEADER_MAP: Dict[str, list[str]] = {
    "date": ["date", "תאריך", "תאריך חשבונית", "יום", "תאריך מכירה", "report date"],
    "store_code": ["store", "סניף", "קוד סניף", "מס סניף", "branch", "store code", "store id"],
    "store_name": ["store name", "שם סניף", "שם הסניף", "branch name"],
    "item_code": ["item", "מק״ט", "מקט", "מק''ט", "מק'ט", "קוד פריט", "sku", "item code"],
    "barcode": ["barcode", "ברקוד", "ean", "upc", "קוד מוצר", "ברקוד פריט"],
    "item_name": ["item name", "שם פריט", "תיאור", "תיאור פריט", "שם המוצר", "description"],
    "brand": ["brand", "מותג", "יצרן", "manufacturer"],
    "category": ["category", "קטגוריה", "קבוצה", "מחלקה", "department"],
    "supplier": ["supplier", "ספק", "שם ספק", "vendor"],
    "quantity": ["quantity", "qty", "כמות", "כמות מכר", "יחידות", "units", "units sold"],
    "gross_sales": [
        "gross sales", "מכר ברוטו", "סכום ברוטו", "ברוטו", "gross", "sales gross",
    ],
    "net_sales": ["net sales", "מכר נטו", "סכום נטו", "נטו", "net", "sales net"],
    "discount_amount": ["discount", "הנחה", "סכום הנחה", "discount amount"],
    "return_quantity": ["returns", "החזרות", "כמות זיכוי", "return qty"],
    "cost_price": ["cost", "מחיר עלות", "עלות", "cost price", "unit cost"],
    "selling_price": ["price", "מחיר", "מחיר מכירה", "selling price", "list price"],
    "inventory_quantity": ["stock", "מלאי", "כמות במלאי", "inventory", "qty on hand"],
    "available_quantity": ["available", "זמין", "מלאי זמין", "available stock"],
    "on_order_quantity": ["on order", "בהזמנה", "הזמנות פתוחות", "on order qty"],
    "snapshot_date": ["snapshot date", "תאריך מלאי", "תאריך עדכון"],
    "region": ["region", "אזור"],
    "store_type": ["store type", "סוג סניף", "type"],
}


_HEBREW_NIQQUD_RE = re.compile(r"[֑-ׇ]")
_PUNCT_RE = re.compile(r"[\"'`׳״.\-_/\\()\[\]{}]+")
_WS_RE = re.compile(r"\s+")


def _norm(s: str) -> str:
    if s is None:
        return ""
    s = unicodedata.normalize("NFKC", str(s))
    s = _HEBREW_NIQQUD_RE.sub("", s)
    s = _PUNCT_RE.sub(" ", s)
    s = _WS_RE.sub(" ", s).strip().lower()
    return s


_LOOKUP: Dict[str, str] = {}
for canonical, variants in HEADER_MAP.items():
    _LOOKUP[_norm(canonical)] = canonical
    for v in variants:
        _LOOKUP[_norm(v)] = canonical


def map_header(header: str) -> str | None:
    return _LOOKUP.get(_norm(header))


def map_headers(headers: Iterable[str]) -> tuple[Dict[str, str], list[str]]:
    """
    Returns (mapping, unmapped):
      mapping: source_header -> canonical_field
      unmapped: list of source headers we could not resolve
    """
    mapping: Dict[str, str] = {}
    unmapped: list[str] = []
    for h in headers:
        canonical = map_header(h)
        if canonical:
            mapping[h] = canonical
        else:
            if h is not None and str(h).strip():
                unmapped.append(str(h))
    return mapping, unmapped
