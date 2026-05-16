from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from ..models import Brand, InventorySnapshot, Item, Sale, Store


def _latest_inventory_per_item_store(db: Session) -> dict[tuple[int, int], InventorySnapshot]:
    latest_dates = (
        select(
            InventorySnapshot.store_id,
            InventorySnapshot.item_id,
            func.max(InventorySnapshot.snapshot_date).label("d"),
        )
        .group_by(InventorySnapshot.store_id, InventorySnapshot.item_id)
        .subquery()
    )
    rows = db.execute(
        select(InventorySnapshot)
        .join(
            latest_dates,
            and_(
                InventorySnapshot.store_id == latest_dates.c.store_id,
                InventorySnapshot.item_id == latest_dates.c.item_id,
                InventorySnapshot.snapshot_date == latest_dates.c.d,
            ),
        )
    ).scalars().all()
    return {(r.store_id, r.item_id): r for r in rows}


def _sales_velocity(
    db: Session, days: int = 30
) -> dict[tuple[int, int], float]:
    """Units per day per (store, item) over the last N days."""
    end = date.today()
    start = end - timedelta(days=days - 1)
    q = (
        select(
            Sale.store_id,
            Sale.item_id,
            func.coalesce(func.sum(Sale.quantity), 0.0),
        )
        .where(Sale.date >= start, Sale.date <= end, Sale.item_id.is_not(None))
        .group_by(Sale.store_id, Sale.item_id)
    )
    return {(s, i): float(u or 0) / days for s, i, u in db.execute(q).all()}


def detect_inventory_risks(db: Session, days_lookback: int = 30) -> dict:
    inv = _latest_inventory_per_item_store(db)
    vel = _sales_velocity(db, days_lookback)
    items = {i.id: i for i in db.scalars(select(Item)).all()}
    stores = {s.id: s for s in db.scalars(select(Store)).all()}

    fast_low: list[dict] = []
    slow_high: list[dict] = []
    stuck: list[dict] = []
    stockout_strong: list[dict] = []

    for (sid, iid), snap in inv.items():
        v = vel.get((sid, iid), 0.0)
        item = items.get(iid)
        store = stores.get(sid)
        if not item or not store:
            continue
        cover_days = snap.inventory_quantity / v if v > 0 else (999 if snap.inventory_quantity > 0 else 0)

        rec = {
            "store_code": store.store_code,
            "store_name": store.store_name,
            "store_type": store.store_type,
            "item_code": item.item_code,
            "item_name": item.item_name,
            "brand": item.brand.name if item.brand else None,
            "inventory": snap.inventory_quantity,
            "on_order": snap.on_order_quantity,
            "velocity_units_per_day": round(v, 2),
            "days_of_cover": round(cover_days, 1),
        }

        if v >= 0.5 and cover_days <= 7:
            fast_low.append(rec)
            if store.store_type in {"flagship", "general"}:
                stockout_strong.append(rec)
        if v < 0.1 and snap.inventory_quantity >= 20:
            slow_high.append(rec)
        if v == 0 and snap.inventory_quantity >= 10:
            stuck.append(rec)

    fast_low.sort(key=lambda r: r["days_of_cover"])
    slow_high.sort(key=lambda r: r["inventory"], reverse=True)
    stuck.sort(key=lambda r: r["inventory"], reverse=True)

    return {
        "fast_moving_low_stock": fast_low[:50],
        "slow_moving_high_stock": slow_high[:50],
        "stuck_items": stuck[:50],
        "stockout_in_strong_stores": stockout_strong[:25],
        "lookback_days": days_lookback,
    }


def detect_slow_moving_items(db: Session, days_lookback: int = 30) -> list[dict]:
    return detect_inventory_risks(db, days_lookback)["slow_moving_high_stock"]


def detect_fast_moving_low_stock_items(db: Session, days_lookback: int = 30) -> list[dict]:
    return detect_inventory_risks(db, days_lookback)["fast_moving_low_stock"]
