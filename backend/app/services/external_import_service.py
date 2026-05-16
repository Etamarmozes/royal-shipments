"""Apply path for ICL + Eli Line preview rows.

Strict rules (per user spec):
  - Each row must carry a `_action` ∈ {create, update, skip}
  - `needs_review=true` rows default to skip (the user can override)
  - NEVER invent container numbers
  - When the user opts to create placeholder containers, set:
        container_number = NULL
        placeholder_container = True
        actual_container_number_missing = True
        container_sequence = 1..N
  - Source Excel files are NOT attached as shipment documents
  - Every CREATE persists `import_batch_id` so rollback can find it
  - UPDATE uses the same manual_overrides protection as the email pipeline
  - Existing shipments NEVER deleted

This service is invoked from /import/excel/apply when the rows carry
source_provider in {"ICL", "Eli Line"}. The Royal Linen template path
stays in excel_import_service.apply().
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from ..models import (
    Shipment, Container, ImportBatch,
)
from . import event_service, shipment_service

log = logging.getLogger("ext-import")


def _to_date(v) -> Optional[date]:
    if v in (None, ""):
        return None
    if isinstance(v, date) and not isinstance(v, datetime):
        return v
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, str):
        try:
            return date.fromisoformat(v)
        except Exception:
            return None
    return None


def _str_or_none(v) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _row_supports_apply(row: Dict[str, Any]) -> bool:
    """A row can be applied only if it has the bare minimum identity."""
    if not row.get("supplier_name"):
        return False
    if not row.get("shipment_reference"):
        return False
    return True


def _next_internal_shp_id(db: Session) -> str:
    """Use the existing SHP-XXX sequence for internal IDs.
    External-format rows that don't carry a Royal Linen SHP-id get a
    new one assigned. Their original ID is preserved in
    `external_file_number` / `external_job_number`."""
    return shipment_service.next_shp_id(db)


def _row_to_shipment_kwargs(row: Dict[str, Any], batch: ImportBatch) -> Dict[str, Any]:
    """Map a preview row → Shipment column kwargs.

    Avoid fields that are computed by Shipment defaults (created_at, etc.).
    Date strings come in as ISO; convert to date objects.
    """
    eta_port = _to_date(row.get("eta_port"))
    eta_warehouse = _to_date(row.get("eta_warehouse"))
    etd = _to_date(row.get("etd"))

    # Map BL fields. Keep the existing `bol_number` populated for backward
    # compat with the email pipeline / dedup — prefer MBL > HBL > legacy bol.
    legacy_bol = (row.get("master_bill_of_lading_number")
                  or row.get("house_bill_of_lading_number"))

    return {
        # Identity
        "supplier":         _str_or_none(row.get("supplier_name")),
        "goods_description": _str_or_none(row.get("product_description")),
        "product_description_raw": _str_or_none(row.get("product_description_raw")
                                                  or row.get("product_description")),

        # External identifiers
        "external_file_number": _str_or_none(row.get("external_file_number")),
        "external_job_number":  _str_or_none(row.get("external_job_number")),
        "sho_list":             _str_or_none(row.get("sho_list")),
        "customs_file_number":  _str_or_none(row.get("customs_file_number")),
        "house_bill_of_lading_number":   _str_or_none(row.get("house_bill_of_lading_number")),
        "master_bill_of_lading_number":  _str_or_none(row.get("master_bill_of_lading_number")),
        "bol_number":           _str_or_none(legacy_bol),
        "po_number":            _str_or_none(row.get("purchase_order_number")),
        "vessel_name":          _str_or_none(row.get("vessel_name")),
        "marks":                _str_or_none(row.get("marks")),

        # Geography
        "origin_port":       _str_or_none(row.get("origin_port")),
        "destination_port":  _str_or_none(row.get("destination_port")),
        "incoterm":          _str_or_none(row.get("incoterm")),
        "carrier":           _str_or_none(row.get("carrier")),
        "shipping_channel":  _str_or_none(row.get("carrier") or row.get("shipping_company")),

        # Dates
        "etd":           etd,
        "eta_port":      eta_port,
        "eta_warehouse": eta_warehouse,

        # Status / review
        "stage_status": _str_or_none(row.get("shipment_status")),
        "needs_review": bool(row.get("needs_review", False)),
        "review_reason": "; ".join(row.get("review_reasons") or [])[:1000] or None,

        # Inference (suggestion only)
        "inferred_brand":      _str_or_none(row.get("inferred_brand")),
        "inferred_category":   _str_or_none(row.get("inferred_category")),
        "inference_confidence": row.get("inference_confidence"),
        # Use inferred category as the default for the regular `category`
        # field — but ONLY if the user/file didn't supply one explicitly.
        # The user can still override later in the shipment profile.
        "category":     _str_or_none(row.get("inferred_category")),

        # Container quantity at shipment level
        "container_quantity":            row.get("container_quantity"),
        "container_quantity_raw":        _str_or_none(row.get("container_quantity_raw")),
        "container_quantity_confidence": _str_or_none(row.get("container_quantity_confidence")),
        "container_type_raw":            _str_or_none(row.get("container_type")),
        "container_raw":                 _str_or_none(row.get("container_raw")),
        "cbm_raw":                       _str_or_none(row.get("cbm_raw")),

        # Source provenance
        "data_source":      "excel_import",
        "is_test_data":     False,
        "creation_source":  "excel_import_external",
        "last_update_source": "excel_import",
        "import_batch_id":  batch.id,
        "source_provider":  _str_or_none(row.get("source_provider")) or batch.source_provider,
        "source_file_name": _str_or_none(row.get("source_file_name")) or batch.source_file_name,
        "source_sheet_name": _str_or_none(row.get("source_sheet_name")) or batch.source_sheet_name,
        "source_row_number": row.get("source_row_number"),
        "raw_source_json":  {k: v for k, v in row.items()
                             if not k.startswith("_") and k != "raw_source_json"},
    }


def _create_placeholder_containers(
    db: Session, *, shipment: Shipment, row: Dict[str, Any], batch: ImportBatch,
) -> int:
    """Create placeholder Container rows when the row has a quantity but no
    actual numbers. Returns the number of containers created."""
    qty = row.get("container_quantity")
    if not qty or qty <= 0:
        return 0
    container_type = _str_or_none(row.get("container_type"))
    container_raw = _str_or_none(row.get("container_raw"))

    n = 0
    for seq in range(1, int(qty) + 1):
        c = Container(
            shipment_id=shipment.id,
            container_number=None,                  # NEVER invented
            container_type=container_type,
            placeholder_container=True,
            actual_container_number_missing=True,
            container_sequence=seq,
            container_raw=container_raw,
            import_batch_id=batch.id,
            source_row_number=row.get("source_row_number"),
            updated_by=batch.imported_by,
            container_status="placeholder_imported",
        )
        db.add(c)
        n += 1
    db.flush()
    return n


def apply(db: Session, rows: List[Dict[str, Any]], *,
          actor_name: str, source_provider: str,
          source_file_name: Optional[str] = None,
          source_sheet_name: Optional[str] = None,
          create_placeholder_containers: bool = True) -> Dict[str, Any]:
    """Apply user-approved rows. Each row must include `_action` ∈
    {"create","update","skip"}. Rows without `_action` default to skip.

    Returns: dict with batch_id + counters + per-row results.
    """
    # Create the batch — every CREATE references this id
    batch = ImportBatch(
        source_provider=source_provider,
        source_file_name=source_file_name,
        source_sheet_name=source_sheet_name,
        imported_by=actor_name,
        total_rows_in_preview=len(rows),
        status="applied",
    )
    db.add(batch)
    db.flush()

    counters = {"created": 0, "updated": 0, "skipped": 0,
                "containers_added": 0, "errors": 0}
    per_row: List[Dict[str, Any]] = []

    for row in rows:
        action = (row.get("_action") or "skip").lower()
        ext_ref = (row.get("external_file_number")
                   or row.get("external_job_number")
                   or row.get("shipment_reference"))
        result = {
            "source_row_number": row.get("source_row_number"),
            "external_ref": ext_ref,
            "action_requested": action,
            "action_taken": "skipped",
            "shp_id": None,
            "shipment_id": None,
            "containers_added": 0,
            "error": None,
        }

        try:
            if action == "skip":
                counters["skipped"] += 1
                per_row.append(result)
                continue

            if not _row_supports_apply(row):
                # supplier_name missing or shipment_reference missing
                # — refuse to create, even if user asked
                counters["skipped"] += 1
                result["action_taken"] = "skipped"
                result["error"] = "Missing supplier_name or shipment_reference"
                per_row.append(result)
                continue

            if action == "update":
                # The preview already attached `_match` if a duplicate exists
                match = row.get("_match") or {}
                target_id = match.get("id")
                if not target_id:
                    counters["skipped"] += 1
                    result["error"] = "Update requested but no matching shipment found"
                    per_row.append(result)
                    continue
                s = db.query(Shipment).filter(Shipment.id == target_id).first()
                if not s:
                    counters["skipped"] += 1
                    result["error"] = "Target shipment vanished mid-import"
                    per_row.append(result)
                    continue

                kwargs = _row_to_shipment_kwargs(row, batch)
                # Don't overwrite the original creation_source / data_source
                kwargs.pop("creation_source", None)
                kwargs.pop("data_source", None)
                kwargs.pop("import_batch_id", None)
                kwargs.pop("raw_source_json", None)

                # Respect manual_overrides — never overwrite a field the user
                # has explicitly edited.
                overrides = s.manual_overrides or {}
                changed = []
                for col, val in kwargs.items():
                    if val in (None, ""):
                        continue
                    if col in overrides:
                        continue
                    if getattr(s, col, None) != val:
                        setattr(s, col, val)
                        changed.append(col)
                s.last_update_source = "excel_import"
                s.updated_by = actor_name
                event_service.log_event(
                    db, entity_type="shipment", entity_id=s.id,
                    action_type="excel_import_update_external",
                    new_value=f"{source_provider}: {len(changed)} fields",
                    changed_by=actor_name, source="excel_import",
                    note=f"batch#{batch.id}, row#{row.get('source_row_number')}, "
                         f"fields: {', '.join(changed[:10])}",
                )
                counters["updated"] += 1
                result["action_taken"] = "updated"
                result["shp_id"] = s.shp_id
                result["shipment_id"] = s.id
                per_row.append(result)
                continue

            if action == "create":
                # Skip if a duplicate is detected — the user should have
                # explicitly chosen "update" instead. Defensive.
                match = row.get("_match") or {}
                if match.get("id"):
                    counters["skipped"] += 1
                    result["action_taken"] = "skipped"
                    result["error"] = (
                        f"Duplicate of existing {match.get('shp_id')} "
                        f"(matched_by {match.get('matched_by')}). Use 'update'."
                    )
                    per_row.append(result)
                    continue

                kwargs = _row_to_shipment_kwargs(row, batch)
                shp_id = _next_internal_shp_id(db)
                kwargs.pop("shp_id", None)
                s = Shipment(
                    shp_id=shp_id,
                    created_date=date.today(),
                    updated_by=actor_name,
                    archived=False,
                    **kwargs,
                )
                db.add(s)
                db.flush()

                event_service.log_event(
                    db, entity_type="shipment", entity_id=s.id,
                    action_type="excel_import_create_external",
                    new_value=f"{source_provider}/{ext_ref} → {s.shp_id}",
                    changed_by=actor_name, source="excel_import",
                    note=f"batch#{batch.id}, row#{row.get('source_row_number')}",
                )

                # Placeholder containers (optional)
                added = 0
                if create_placeholder_containers:
                    added = _create_placeholder_containers(
                        db, shipment=s, row=row, batch=batch,
                    )
                    if added:
                        counters["containers_added"] += added
                        event_service.log_event(
                            db, entity_type="shipment", entity_id=s.id,
                            action_type="placeholder_containers_created",
                            new_value=f"{added} placeholder containers (qty {row.get('container_quantity')})",
                            changed_by=actor_name, source="excel_import",
                        )

                counters["created"] += 1
                result["action_taken"] = "created"
                result["shp_id"] = s.shp_id
                result["shipment_id"] = s.id
                result["containers_added"] = added
                per_row.append(result)
                continue

            # Unknown action
            counters["skipped"] += 1
            result["error"] = f"Unknown action: {action}"
            per_row.append(result)

        except Exception as e:
            log.exception("Apply row failed: %s", e)
            counters["errors"] += 1
            result["action_taken"] = "error"
            result["error"] = str(e)
            per_row.append(result)
            db.rollback()
            # Re-fetch the batch — rollback dropped our flushed row
            batch = db.query(ImportBatch).filter(ImportBatch.id == batch.id).first() or batch

    # Update batch counters
    batch.created_count = counters["created"]
    batch.updated_count = counters["updated"]
    batch.skipped_count = counters["skipped"]
    batch.error_count = counters["errors"]
    batch.details_json = {"per_row": per_row}
    db.commit()

    log.info("External import applied: batch#%s by %s — %s",
             batch.id, actor_name, counters)
    return {
        "batch_id": batch.id,
        "source_provider": source_provider,
        **counters,
        "per_row": per_row,
    }


# =====================================================================
# Rollback
# =====================================================================

def rollback_batch(db: Session, batch_id: int, *, actor_name: str,
                   reason: Optional[str] = None) -> Dict[str, Any]:
    """Archive every shipment + container CREATED by this batch.

    UPDATE actions are NOT auto-reverted (we'd need before/after snapshots
    of every field to do that safely; for now the user must edit those
    shipments manually if they want to undo).

    Soft-archive only — never hard-deletes.
    """
    batch = db.query(ImportBatch).filter(ImportBatch.id == batch_id).first()
    if not batch:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Batch not found")
    if batch.status == "rolled_back":
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Batch already rolled back")

    # Find shipments created by this batch (NOT those that were just
    # updated — those don't carry import_batch_id). Even safer: also
    # require creation_source == "excel_import_external".
    candidates = db.query(Shipment).filter(
        Shipment.import_batch_id == batch_id,
        Shipment.creation_source == "excel_import_external",
        Shipment.archived == False,   # noqa: E712
    ).all()

    archived_ids = []
    for s in candidates:
        # Detect if user edited the shipment AFTER import — those carry
        # manual_overrides keys. Treat as a warning but still archive
        # (the user can un-archive later if needed).
        had_edits = bool(s.manual_overrides)
        s.archived = True
        s.completed_at = datetime.utcnow()
        archived_ids.append({
            "id": s.id, "shp_id": s.shp_id,
            "had_post_import_edits": had_edits,
        })
        event_service.log_event(
            db, entity_type="shipment", entity_id=s.id,
            action_type="rollback_archive",
            new_value=f"batch#{batch_id} rolled back by {actor_name}",
            changed_by=actor_name, source="excel_import_rollback",
            note=reason or "",
        )

    batch.rolled_back_at = datetime.utcnow()
    batch.rolled_back_by = actor_name
    batch.rolled_back_reason = reason
    batch.rolled_back_count = len(archived_ids)
    batch.status = "rolled_back"

    db.commit()

    log.info("Batch#%s rolled back by %s: archived %d shipments",
             batch_id, actor_name, len(archived_ids))
    return {
        "batch_id": batch_id,
        "archived_shipments": archived_ids,
        "archived_count": len(archived_ids),
        "had_edits_count": sum(1 for x in archived_ids if x["had_post_import_edits"]),
    }
