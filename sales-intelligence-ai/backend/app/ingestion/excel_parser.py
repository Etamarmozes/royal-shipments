"""
Read Excel/CSV into a list of dicts with normalized canonical column names.
Numbers and dates are coerced safely.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from .column_normalizer import map_headers


_CURRENCY_RE = re.compile(r"[₪$€£,\s]")


def _coerce_number(v: Any) -> float | None:
    if v is None:
        return None
    if isinstance(v, (int, float)) and not pd.isna(v):
        return float(v)
    s = str(v).strip()
    if not s or s.lower() in {"nan", "none", "null", "-"}:
        return None
    if s.endswith("%"):
        try:
            return float(_CURRENCY_RE.sub("", s[:-1])) / 100.0
        except ValueError:
            return None
    s = _CURRENCY_RE.sub("", s)
    try:
        return float(s)
    except ValueError:
        return None


def _coerce_date(v: Any) -> date | None:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if isinstance(v, (int, float)):
        # Excel serial date
        try:
            return (datetime(1899, 12, 30) + pd.Timedelta(days=float(v))).date()
        except Exception:
            return None
    s = str(v).strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y/%m/%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    try:
        return pd.to_datetime(s, dayfirst=True, errors="raise").date()
    except Exception:
        return None


_NUMERIC_FIELDS = {
    "quantity",
    "gross_sales",
    "net_sales",
    "discount_amount",
    "return_quantity",
    "cost_price",
    "selling_price",
    "inventory_quantity",
    "available_quantity",
    "on_order_quantity",
}
_DATE_FIELDS = {"date", "snapshot_date"}


def read_file(path: Path) -> list[tuple[str, pd.DataFrame]]:
    """
    Returns a list of (sheet_name, DataFrame). For CSV the sheet name is the file stem.
    """
    suffix = path.suffix.lower()
    if suffix in {".csv", ".tsv"}:
        sep = "\t" if suffix == ".tsv" else ","
        df = pd.read_csv(path, sep=sep, dtype=object, encoding="utf-8-sig")
        return [(path.stem, df)]
    if suffix in {".xlsx", ".xls", ".xlsm"}:
        engine = "openpyxl" if suffix in {".xlsx", ".xlsm"} else None
        with pd.ExcelFile(path, engine=engine) as xls:
            return [(name, xls.parse(name, dtype=object)) for name in xls.sheet_names]
    raise ValueError(f"Unsupported file type: {suffix}")


def normalize_dataframe(df: pd.DataFrame) -> tuple[list[dict], list[str], list[str]]:
    """
    Returns (rows, unmapped_headers, warnings).
    Each row is a dict keyed by canonical field name, with numbers/dates coerced.
    """
    if df.empty:
        return [], [], []

    headers = list(df.columns)
    mapping, unmapped = map_headers(headers)

    if not mapping:
        return [], unmapped, ["no recognized columns"]

    rename = {src: canon for src, canon in mapping.items()}
    df2 = df.rename(columns=rename)
    canonical_cols = list(rename.values())
    df2 = df2.loc[:, [c for c in canonical_cols if c in df2.columns]]

    rows: list[dict] = []
    warnings: list[str] = []

    for idx, raw in df2.iterrows():
        row: dict = {}
        empty = True
        for col, val in raw.items():
            if pd.isna(val):
                row[col] = None
                continue
            if col in _NUMERIC_FIELDS:
                num = _coerce_number(val)
                row[col] = num
                if num is not None:
                    empty = False
            elif col in _DATE_FIELDS:
                d = _coerce_date(val)
                row[col] = d
                if d is not None:
                    empty = False
            else:
                s = str(val).strip()
                row[col] = s if s else None
                if s:
                    empty = False
        if not empty:
            rows.append(row)

    return rows, unmapped, warnings
