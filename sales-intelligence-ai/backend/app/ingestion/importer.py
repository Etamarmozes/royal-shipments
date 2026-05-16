"""
End-to-end import pipeline. Reads a file, detects type, normalizes,
upserts dimensions, writes facts, moves the file, and writes an ImportLog row.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import date, datetime
from pathlib import Path
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import session_scope
from ..models import (
    Brand,
    Category,
    ImportLog,
    InventorySnapshot,
    Item,
    Sale,
    Store,
    Supplier,
)
from ..utils.logging import get_logger
from .excel_parser import normalize_dataframe, read_file
from .report_detector import detect_report_type

log = get_logger(__name__)


SUPPORTED_SUFFIXES = {".xlsx", ".xls", ".xlsm", ".csv", ".tsv"}


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _move(src: Path, dst_dir: Path) -> Path:
    dst_dir.mkdir(parents=True, exist_ok=True)
    target = dst_dir / src.name
    if target.exists():
        target = dst_dir / f"{src.stem}_{datetime.now().strftime('%Y%m%d%H%M%S')}{src.suffix}"
    shutil.move(str(src), str(target))
    return target


def _get_or_create_store(db: Session, code: str | None, name: str | None) -> Store | None:
    if not code and not name:
        return None
    code = code or name
    name = name or code
    store = db.scalar(select(Store).where(Store.store_code == code))
    if store is None:
        store = Store(store_code=str(code), store_name=str(name), active=True)
        db.add(store)
        db.flush()
    return store


def _get_or_create_brand(db: Session, name: str | None) -> Brand | None:
    if not name:
        return None
    b = db.scalar(select(Brand).where(Brand.name == name))
    if b is None:
        b = Brand(name=name)
        db.add(b)
        db.flush()
    return b


def _get_or_create_category(db: Session, name: str | None) -> Category | None:
    if not name:
        return None
    c = db.scalar(select(Category).where(Category.name == name))
    if c is None:
        c = Category(name=name)
        db.add(c)
        db.flush()
    return c


def _get_or_create_supplier(db: Session, name: str | None) -> Supplier | None:
    if not name:
        return None
    s = db.scalar(select(Supplier).where(Supplier.name == name))
    if s is None:
        s = Supplier(name=name)
        db.add(s)
        db.flush()
    return s


def _resolve_item(
    db: Session,
    item_code: str | None,
    barcode: str | None,
    item_name: str | None,
    brand_name: str | None,
    category_name: str | None,
) -> Item | None:
    if not item_code and not barcode:
        return None
    item: Item | None = None
    if item_code:
        item = db.scalar(select(Item).where(Item.item_code == str(item_code)))
    if item is None and barcode:
        item = db.scalar(select(Item).where(Item.barcode == str(barcode)))
    if item is None:
        if not item_code and not barcode:
            return None
        item = Item(
            item_code=str(item_code or barcode),
            barcode=str(barcode) if barcode else None,
            item_name=str(item_name or item_code or barcode),
            brand_id=_get_or_create_brand(db, brand_name).id if brand_name else None,
            category_id=_get_or_create_category(db, category_name).id if category_name else None,
            active=True,
        )
        db.add(item)
        db.flush()
    else:
        # backfill missing fields without overwriting existing
        if barcode and not item.barcode:
            item.barcode = str(barcode)
        if brand_name and not item.brand_id:
            b = _get_or_create_brand(db, brand_name)
            if b:
                item.brand_id = b.id
        if category_name and not item.category_id:
            c = _get_or_create_category(db, category_name)
            if c:
                item.category_id = c.id
    return item


def _write_sales(db: Session, rows: Iterable[dict], import_log_id: int) -> tuple[int, int]:
    inserted = skipped = 0
    for row in rows:
        d = row.get("date")
        store_code = row.get("store_code")
        if not d or not store_code:
            skipped += 1
            continue
        store = _get_or_create_store(db, store_code, row.get("store_name"))
        item = _resolve_item(
            db,
            row.get("item_code"),
            row.get("barcode"),
            row.get("item_name"),
            row.get("brand"),
            row.get("category"),
        )
        gross = row.get("gross_sales") or 0.0
        net = row.get("net_sales")
        disc = row.get("discount_amount") or 0.0
        if net is None:
            net = float(gross) - float(disc)
        cost_amount = None
        margin = None
        if item and item.cost_price is not None and row.get("quantity") is not None:
            cost_amount = float(item.cost_price) * float(row["quantity"])
            margin = float(net) - cost_amount
        sale = Sale(
            date=d,
            store_id=store.id,
            item_id=item.id if item else None,
            barcode=row.get("barcode"),
            quantity=float(row.get("quantity") or 0.0),
            gross_sales=float(gross),
            net_sales=float(net or 0.0),
            discount_amount=float(disc or 0.0),
            return_quantity=float(row.get("return_quantity") or 0.0),
            cost_amount=cost_amount,
            gross_margin_amount=margin,
            source_file_id=import_log_id,
        )
        db.add(sale)
        inserted += 1
    return inserted, skipped


def _write_inventory(db: Session, rows: Iterable[dict], import_log_id: int) -> tuple[int, int]:
    inserted = skipped = 0
    for row in rows:
        snap = row.get("snapshot_date") or row.get("date") or date.today()
        store_code = row.get("store_code")
        if not store_code:
            skipped += 1
            continue
        store = _get_or_create_store(db, store_code, row.get("store_name"))
        item = _resolve_item(
            db,
            row.get("item_code"),
            row.get("barcode"),
            row.get("item_name"),
            row.get("brand"),
            row.get("category"),
        )
        if item is None:
            skipped += 1
            continue
        snap_row = InventorySnapshot(
            snapshot_date=snap,
            store_id=store.id,
            item_id=item.id,
            barcode=row.get("barcode"),
            inventory_quantity=float(row.get("inventory_quantity") or 0.0),
            available_quantity=row.get("available_quantity"),
            on_order_quantity=row.get("on_order_quantity"),
            source_file_id=import_log_id,
        )
        db.add(snap_row)
        inserted += 1
    return inserted, skipped


def _write_items_master(db: Session, rows: Iterable[dict]) -> tuple[int, int]:
    inserted = updated = 0
    for row in rows:
        code = row.get("item_code")
        if not code:
            continue
        item = _resolve_item(
            db,
            code,
            row.get("barcode"),
            row.get("item_name"),
            row.get("brand"),
            row.get("category"),
        )
        if item is None:
            continue
        if row.get("supplier"):
            s = _get_or_create_supplier(db, row["supplier"])
            if s:
                item.supplier_id = s.id
        if row.get("cost_price") is not None:
            item.cost_price = float(row["cost_price"])
        if row.get("selling_price") is not None:
            item.selling_price = float(row["selling_price"])
        if row.get("item_name"):
            item.item_name = row["item_name"]
        inserted += 1
    return inserted, 0


def _write_stores_master(db: Session, rows: Iterable[dict]) -> tuple[int, int]:
    n = 0
    for row in rows:
        code = row.get("store_code")
        if not code:
            continue
        store = _get_or_create_store(db, code, row.get("store_name"))
        if row.get("region"):
            store.region = row["region"]
        if row.get("store_type"):
            store.store_type = row["store_type"]
        n += 1
    return n, 0


def import_file(path: Path) -> dict:
    """Import a single file. Returns a summary dict."""
    file_hash = _hash_file(path)

    with session_scope() as db:
        existing = db.scalar(select(ImportLog).where(ImportLog.file_hash == file_hash))
        if existing:
            log.info("import.skip duplicate hash file=%s", path.name)
            _move(path, settings.ARCHIVE_DIR)
            return {
                "status": "skipped",
                "reason": "duplicate_hash",
                "file": path.name,
                "import_log_id": existing.id,
            }

    try:
        sheets = read_file(path)
    except Exception as e:
        log.exception("import.read_error file=%s", path.name)
        return _record_failure(path, file_hash, "read_error", str(e), "unknown")

    all_rows: list[dict] = []
    detection = None
    unmapped_all: list[str] = []

    for sheet_name, df in sheets:
        rows, unmapped, _ = normalize_dataframe(df)
        if not rows:
            continue
        unmapped_all.extend(unmapped)
        guess = detect_report_type(path.name, df.columns)
        if detection is None or (
            guess.confidence in {"high", "medium"} and detection.confidence == "low"
        ):
            detection = guess
        all_rows.extend(rows)

    if not all_rows or detection is None or detection.report_type == "unknown":
        rt = detection.report_type if detection else "unknown"
        return _record_failure(
            path,
            file_hash,
            "unknown_report_type",
            f"could not detect report type; unmapped={unmapped_all[:8]}",
            rt,
            rows_detected=len(all_rows),
        )

    rows_detected = len(all_rows)
    inserted = 0
    skipped = 0
    data_min = data_max = None
    warnings: list[str] = []
    if unmapped_all:
        warnings.append(f"unmapped_columns={list(set(unmapped_all))}")

    try:
        with session_scope() as db:
            log_row = ImportLog(
                file_name=path.name,
                original_path=str(path),
                file_hash=file_hash,
                report_type=detection.report_type,
                status="partial",
                rows_detected=rows_detected,
            )
            db.add(log_row)
            db.flush()

            if detection.report_type == "sales":
                inserted, skipped = _write_sales(db, all_rows, log_row.id)
                dates = [r["date"] for r in all_rows if r.get("date")]
                if dates:
                    data_min, data_max = min(dates), max(dates)
            elif detection.report_type == "inventory":
                inserted, skipped = _write_inventory(db, all_rows, log_row.id)
                dates = [r.get("snapshot_date") or r.get("date") for r in all_rows]
                dates = [d for d in dates if d]
                if dates:
                    data_min, data_max = min(dates), max(dates)
            elif detection.report_type == "items_master":
                inserted, skipped = _write_items_master(db, all_rows)
            elif detection.report_type == "stores_master":
                inserted, skipped = _write_stores_master(db, all_rows)
            else:
                skipped = rows_detected

            log_row.rows_imported = inserted
            log_row.rows_failed = skipped
            log_row.data_date_min = data_min
            log_row.data_date_max = data_max
            log_row.status = (
                "success" if skipped == 0 and inserted > 0 else
                "partial" if inserted > 0 else
                "failed"
            )
            log_row.warnings = json.dumps(warnings, ensure_ascii=False) if warnings else None
            log_id = log_row.id
            final_status = log_row.status
    except Exception as e:
        log.exception("import.write_error file=%s", path.name)
        return _record_failure(path, file_hash, "write_error", str(e), detection.report_type, rows_detected)

    dest = settings.IMPORTED_DIR if final_status != "failed" else settings.FAILED_DIR
    moved_to = _move(path, dest)
    log.info(
        "import.done file=%s type=%s status=%s inserted=%d skipped=%d",
        path.name, detection.report_type, final_status, inserted, skipped,
    )
    return {
        "status": final_status,
        "file": path.name,
        "moved_to": str(moved_to),
        "report_type": detection.report_type,
        "confidence": detection.confidence,
        "rows_detected": rows_detected,
        "rows_imported": inserted,
        "rows_failed": skipped,
        "import_log_id": log_id,
        "warnings": warnings,
    }


def _record_failure(
    path: Path,
    file_hash: str,
    reason: str,
    detail: str,
    report_type: str,
    rows_detected: int = 0,
) -> dict:
    with session_scope() as db:
        log_row = ImportLog(
            file_name=path.name,
            original_path=str(path),
            file_hash=file_hash,
            report_type=report_type or "unknown",
            status="failed",
            rows_detected=rows_detected,
            errors=json.dumps({"reason": reason, "detail": detail}, ensure_ascii=False),
        )
        db.add(log_row)
        db.flush()
        log_id = log_row.id

    moved = _move(path, settings.FAILED_DIR)
    err_path = moved.with_suffix(moved.suffix + ".error.json")
    err_path.write_text(
        json.dumps(
            {
                "file": path.name,
                "reason": reason,
                "detail": detail,
                "report_type_guess": report_type,
                "imported_at": datetime.utcnow().isoformat() + "Z",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return {
        "status": "failed",
        "file": path.name,
        "reason": reason,
        "detail": detail,
        "moved_to": str(moved),
        "import_log_id": log_id,
    }


def import_all_pending() -> list[dict]:
    """Import every supported file currently sitting in data/comax_reports/."""
    results: list[dict] = []
    if not settings.COMAX_REPORTS_DIR.exists():
        return results
    for entry in sorted(settings.COMAX_REPORTS_DIR.iterdir()):
        if entry.is_file() and entry.suffix.lower() in SUPPORTED_SUFFIXES:
            try:
                results.append(import_file(entry))
            except Exception as e:
                log.exception("import.unexpected file=%s", entry.name)
                results.append({"status": "failed", "file": entry.name, "detail": str(e)})
    return results
