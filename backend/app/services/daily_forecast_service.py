"""Daily pallet forecast — day-by-day breakdown of expected arrivals.

For each day in the next N days, aggregates:
- containers arriving (by effective ETA Israel)
- shipments / suppliers
- total cartons + CBM
- estimated pallets (sum of estimated_pallets_final from container)
- containers missing carton dimensions (so user knows the calc is approximate)
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Dict, List
from sqlalchemy.orm import Session, joinedload

from ..models import Container, Shipment

log = logging.getLogger("daily_forecast")


def _has_carton_dims(c: Container) -> bool:
    return bool(
        c.carton_length_cm and c.carton_length_cm > 0
        and c.carton_width_cm and c.carton_width_cm > 0
        and c.carton_height_cm and c.carton_height_cm > 0
    )


def _effective_eta(c: Container) -> date | None:
    return c.eta_israel or (c.shipment.eta_israel if c.shipment else None)


def daily_pallet_forecast(db: Session, days: int = 14) -> List[Dict[str, Any]]:
    """Return a list of `days` day-buckets, starting from today."""
    today = date.today()
    containers = (
        db.query(Container).options(joinedload(Container.shipment)).all()
    )

    # Group by date
    by_day: Dict[date, List[Container]] = {}
    for c in containers:
        s = c.shipment
        if s and s.archived:
            continue
        eta = _effective_eta(c)
        if not eta:
            continue
        if today <= eta < today + timedelta(days=days):
            by_day.setdefault(eta, []).append(c)

    results: List[Dict[str, Any]] = []
    for i in range(days):
        d = today + timedelta(days=i)
        day_containers = by_day.get(d, [])
        suppliers: set[str] = set()
        shipment_ids: set[int] = set()
        total_cartons = 0
        total_cbm = 0.0
        total_pallets = 0
        missing_dims = 0

        for c in day_containers:
            if c.shipment:
                shipment_ids.add(c.shipment.id)
                if c.shipment.supplier:
                    suppliers.add(c.shipment.supplier)
            total_cartons += c.boxes_total or 0
            total_cbm += c.cbm or 0
            if c.estimated_pallets_final:
                total_pallets += c.estimated_pallets_final
            if not _has_carton_dims(c):
                missing_dims += 1

        results.append({
            "date": d.isoformat(),
            "weekday": d.strftime("%A"),
            "containers_arriving": len(day_containers),
            "shipment_ids": sorted(shipment_ids),
            "suppliers": sorted(suppliers),
            "total_cartons": total_cartons,
            "total_cbm": round(total_cbm, 2),
            "estimated_pallets": total_pallets,
            "missing_carton_dimensions": missing_dims,
            "is_today": d == today,
            "is_tomorrow": d == today + timedelta(days=1),
        })
    return results


def daily_kpis(db: Session) -> Dict[str, Any]:
    """KPIs derived from the daily forecast — used by the dashboard."""
    forecast = daily_pallet_forecast(db, days=14)
    today = next((d for d in forecast if d["is_today"]), None)
    tomorrow = next((d for d in forecast if d["is_tomorrow"]), None)
    next_7 = forecast[:7]

    # Count containers in active shipments missing carton dimensions / ETA
    containers = db.query(Container).options(joinedload(Container.shipment)).all()
    missing_dims_total = 0
    missing_eta_shipments: set[int] = set()
    for c in containers:
        if c.shipment and c.shipment.archived:
            continue
        if not _has_carton_dims(c):
            missing_dims_total += 1
        if not _effective_eta(c) and c.shipment:
            missing_eta_shipments.add(c.shipment.id)

    return {
        "pallets_today": today["estimated_pallets"] if today else 0,
        "containers_today": today["containers_arriving"] if today else 0,
        "pallets_tomorrow": tomorrow["estimated_pallets"] if tomorrow else 0,
        "containers_tomorrow": tomorrow["containers_arriving"] if tomorrow else 0,
        "pallets_next_7_days": sum(d["estimated_pallets"] for d in next_7),
        "containers_next_7_days": sum(d["containers_arriving"] for d in next_7),
        "containers_missing_carton_dimensions": missing_dims_total,
        "shipments_missing_eta": len(missing_eta_shipments),
    }
