"""Warehouse receiving — record what was actually received vs expected.

This is intentionally a thin layer on Container; we don't model a separate
receiving event table for V1. Discrepancies create alerts.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import Container, Shipment
from . import event_service, alert_service

log = logging.getLogger("receiving")

VALID_STATUSES = {"not_received", "partially_received", "received", "discrepancy"}

# Allowed delta % between expected and actual cartons before flagging
CARTON_TOLERANCE_PCT = 0.02   # 2%
PALLET_TOLERANCE_ABS = 1      # 1 pallet


def _expected_pallets(c: Container) -> Optional[int]:
    return c.estimated_pallets_final


def receive_container(
    db: Session,
    container_id: int,
    *,
    received_cartons_actual: Optional[int] = None,
    received_pallets_actual: Optional[int] = None,
    received_notes: Optional[str] = None,
    received_by: str = "warehouse",
    receiving_status: Optional[str] = None,
) -> Container:
    c = db.query(Container).filter(Container.id == container_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Container not found")

    old = {
        "received_cartons_actual": c.received_cartons_actual,
        "received_pallets_actual": c.received_pallets_actual,
        "receiving_status": c.receiving_status,
    }

    if received_cartons_actual is not None:
        c.received_cartons_actual = received_cartons_actual
    if received_pallets_actual is not None:
        c.received_pallets_actual = received_pallets_actual
    if received_notes is not None:
        c.received_notes = received_notes
    c.received_by = received_by
    c.received_at = datetime.utcnow()

    # Decide receiving_status if not explicitly given
    if receiving_status:
        if receiving_status not in VALID_STATUSES:
            raise HTTPException(status_code=400, detail=f"סטטוס לא חוקי: {receiving_status}")
        c.receiving_status = receiving_status
    else:
        c.receiving_status = _decide_status(c)

    # Discrepancy alerts
    discrepancies: list[str] = []
    expected_cartons = c.boxes_total
    if (
        expected_cartons and c.received_cartons_actual is not None
        and expected_cartons > 0
        and c.received_cartons_actual != expected_cartons
    ):
        delta = c.received_cartons_actual - expected_cartons
        pct = abs(delta) / expected_cartons
        if pct > CARTON_TOLERANCE_PCT:
            note = f"קרטונים: צפוי {expected_cartons}, התקבל {c.received_cartons_actual} (פער {delta:+d})"
            discrepancies.append(note)
            alert_service.create_alert(
                db,
                alert_type="receiving_carton_discrepancy",
                title=f"פער בכמות קרטונים — {c.container_number}",
                description=note,
                severity="high",
                container_id=c.id,
                shipment_id=c.shipment_id,
            )

    expected_pallets = _expected_pallets(c)
    if (
        expected_pallets and c.received_pallets_actual is not None
        and abs(c.received_pallets_actual - expected_pallets) > PALLET_TOLERANCE_ABS
    ):
        delta = c.received_pallets_actual - expected_pallets
        note = f"משטחים: צפוי {expected_pallets}, התקבל {c.received_pallets_actual} (פער {delta:+d})"
        discrepancies.append(note)
        alert_service.create_alert(
            db,
            alert_type="receiving_pallet_discrepancy",
            title=f"פער בכמות משטחים — {c.container_number}",
            description=note,
            severity="medium",
            container_id=c.id,
            shipment_id=c.shipment_id,
        )

    if discrepancies:
        c.receiving_status = "discrepancy"

    # Log a single summary event with the changes
    event_service.log_event(
        db,
        entity_type="container", entity_id=c.id,
        action_type="receive",
        new_value=(
            f"status={c.receiving_status} cartons={c.received_cartons_actual} "
            f"pallets={c.received_pallets_actual}"
        ),
        old_value=str(old),
        changed_by=received_by, source="warehouse",
        note="; ".join(discrepancies) if discrepancies else None,
    )
    db.commit()
    db.refresh(c)
    log.info("Container %s received → status=%s discrepancies=%s",
             c.container_number, c.receiving_status, len(discrepancies))
    return c


def _decide_status(c: Container) -> str:
    """If no actual carton/pallet count given, status='not_received'.
    If actual exists and matches → 'received'. Otherwise caller may force.
    """
    if c.received_cartons_actual is None and c.received_pallets_actual is None:
        return "not_received"
    expected = c.boxes_total
    if expected and c.received_cartons_actual is not None:
        if c.received_cartons_actual == expected:
            return "received"
        if 0 < c.received_cartons_actual < expected:
            return "partially_received"
    return "received"
