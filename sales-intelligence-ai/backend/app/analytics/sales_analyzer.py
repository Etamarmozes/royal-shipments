from __future__ import annotations

from datetime import date
from typing import Any, Optional

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from ..models import Brand, Category, Item, Sale, Store
from .periods import Period, resolve_period


def _pct(curr: float, prev: float) -> Optional[float]:
    if prev is None or prev == 0:
        return None
    return round((curr - prev) / prev * 100, 1)


def _filters(q, store_ids=None, brand_ids=None, category_ids=None):
    if store_ids:
        q = q.where(Sale.store_id.in_(store_ids))
    if brand_ids or category_ids:
        q = q.join(Item, Item.id == Sale.item_id, isouter=True)
        if brand_ids:
            q = q.where(Item.brand_id.in_(brand_ids))
        if category_ids:
            q = q.where(Item.category_id.in_(category_ids))
    return q


def get_sales_summary(
    db: Session,
    date_range: Any = "this_month",
    store_ids: list[int] | None = None,
    brand_ids: list[int] | None = None,
    category_ids: list[int] | None = None,
) -> dict:
    p = resolve_period(date_range)
    prev = p.previous()

    def totals(period: Period) -> dict:
        q = select(
            func.coalesce(func.sum(Sale.gross_sales), 0.0),
            func.coalesce(func.sum(Sale.net_sales), 0.0),
            func.coalesce(func.sum(Sale.quantity), 0.0),
            func.count(Sale.id),
            func.coalesce(func.sum(Sale.gross_margin_amount), 0.0),
        ).where(and_(Sale.date >= period.start, Sale.date <= period.end))
        q = _filters(q, store_ids, brand_ids, category_ids)
        gross, net, units, txns, margin = db.execute(q).one()
        avg_price = (net / units) if units else 0.0
        return {
            "gross_sales": float(gross or 0),
            "net_sales": float(net or 0),
            "units": float(units or 0),
            "transactions": int(txns or 0),
            "avg_selling_price": round(float(avg_price), 2),
            "gross_margin": float(margin or 0),
        }

    curr = totals(p)
    prev_t = totals(prev)
    return {
        "period_label": p.label,
        "period_from": p.start.isoformat(),
        "period_to": p.end.isoformat(),
        **curr,
        "vs_previous_period": {
            "previous_label": prev.label,
            "previous_net_sales": prev_t["net_sales"],
            "delta_pct": _pct(curr["net_sales"], prev_t["net_sales"]),
            "delta_abs": round(curr["net_sales"] - prev_t["net_sales"], 2),
        },
    }


def get_top_items(
    db: Session,
    date_range: Any = "this_month",
    limit: int = 10,
    by: str = "net_sales",
    store_ids: list[int] | None = None,
) -> list[dict]:
    p = resolve_period(date_range)
    metric_col = {
        "net_sales": func.sum(Sale.net_sales),
        "units": func.sum(Sale.quantity),
        "margin": func.sum(Sale.gross_margin_amount),
    }.get(by, func.sum(Sale.net_sales))

    q = (
        select(
            Item.id,
            Item.item_name,
            Brand.name,
            Category.name,
            metric_col.label("value"),
            func.sum(Sale.quantity).label("units"),
        )
        .join(Item, Item.id == Sale.item_id)
        .join(Brand, Brand.id == Item.brand_id, isouter=True)
        .join(Category, Category.id == Item.category_id, isouter=True)
        .where(Sale.date >= p.start, Sale.date <= p.end)
        .group_by(Item.id, Item.item_name, Brand.name, Category.name)
        .order_by(metric_col.desc())
        .limit(limit)
    )
    if store_ids:
        q = q.where(Sale.store_id.in_(store_ids))

    rows = db.execute(q).all()
    total = sum(float(r.value or 0) for r in rows) or 1.0
    return [
        {
            "item_id": r.id,
            "item_name": r.item_name,
            "brand": r[2],
            "category": r[3],
            "value": round(float(r.value or 0), 2),
            "units": float(r.units or 0),
            "share_pct": round(float(r.value or 0) / total * 100, 1),
        }
        for r in rows
    ]


def get_bottom_items(
    db: Session,
    date_range: Any = "this_month",
    limit: int = 10,
    by: str = "net_sales",
    store_ids: list[int] | None = None,
) -> list[dict]:
    p = resolve_period(date_range)
    metric_col = {
        "net_sales": func.sum(Sale.net_sales),
        "units": func.sum(Sale.quantity),
    }.get(by, func.sum(Sale.net_sales))

    q = (
        select(
            Item.id,
            Item.item_name,
            Brand.name,
            metric_col.label("value"),
        )
        .join(Item, Item.id == Sale.item_id)
        .join(Brand, Brand.id == Item.brand_id, isouter=True)
        .where(Sale.date >= p.start, Sale.date <= p.end)
        .group_by(Item.id, Item.item_name, Brand.name)
        .having(metric_col > 0)
        .order_by(metric_col.asc())
        .limit(limit)
    )
    if store_ids:
        q = q.where(Sale.store_id.in_(store_ids))

    return [
        {"item_id": r.id, "item_name": r.item_name, "brand": r[2], "value": round(float(r.value or 0), 2)}
        for r in db.execute(q).all()
    ]


def get_store_ranking(
    db: Session,
    date_range: Any = "this_month",
    by: str = "net_sales",
) -> list[dict]:
    p = resolve_period(date_range)
    prev = p.previous()

    def by_period(period: Period) -> dict[int, float]:
        q = (
            select(Sale.store_id, func.sum(Sale.net_sales))
            .where(Sale.date >= period.start, Sale.date <= period.end)
            .group_by(Sale.store_id)
        )
        return {sid: float(v or 0) for sid, v in db.execute(q).all()}

    curr = by_period(p)
    prevm = by_period(prev)
    stores = {s.id: s for s in db.scalars(select(Store)).all()}

    rows = []
    for sid, val in sorted(curr.items(), key=lambda x: x[1], reverse=True):
        s = stores.get(sid)
        if not s:
            continue
        prev_val = prevm.get(sid, 0.0)
        rows.append(
            {
                "store_id": sid,
                "store_code": s.store_code,
                "store_name": s.store_name,
                "store_type": s.store_type,
                "value": round(val, 2),
                "vs_prev_pct": _pct(val, prev_val),
                "vs_prev_abs": round(val - prev_val, 2),
            }
        )
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return rows


def analyze_store_performance(db: Session, date_range: Any = "this_month") -> dict:
    ranking = get_store_ranking(db, date_range)
    if not ranking:
        return {"ranking": [], "weak_stores": [], "median": 0.0}
    values = sorted([r["value"] for r in ranking])
    median = values[len(values) // 2]
    weak = [r for r in ranking if r["value"] < 0.7 * median]
    return {"ranking": ranking, "weak_stores": weak, "median": median}


def get_brand_performance(db: Session, brand_name: str, date_range: Any = "this_month") -> dict:
    p = resolve_period(date_range)
    brand = db.scalar(select(Brand).where(func.lower(Brand.name) == brand_name.lower()))
    if not brand:
        return {"brand": brand_name, "found": False, "total": 0.0, "by_store": []}

    total_q = (
        select(func.coalesce(func.sum(Sale.net_sales), 0.0), func.coalesce(func.sum(Sale.quantity), 0.0))
        .join(Item, Item.id == Sale.item_id)
        .where(Item.brand_id == brand.id, Sale.date >= p.start, Sale.date <= p.end)
    )
    total, units = db.execute(total_q).one()

    by_store_q = (
        select(Store.store_code, Store.store_name, Store.store_type,
               func.sum(Sale.net_sales), func.sum(Sale.quantity))
        .join(Item, Item.id == Sale.item_id)
        .join(Store, Store.id == Sale.store_id)
        .where(Item.brand_id == brand.id, Sale.date >= p.start, Sale.date <= p.end)
        .group_by(Store.store_code, Store.store_name, Store.store_type)
        .order_by(func.sum(Sale.net_sales).desc())
    )
    by_store = [
        {"store_code": c, "store_name": n, "store_type": t,
         "net_sales": round(float(v or 0), 2), "units": float(u or 0)}
        for c, n, t, v, u in db.execute(by_store_q).all()
    ]
    return {
        "brand": brand.name,
        "found": True,
        "period_label": p.label,
        "net_sales": round(float(total or 0), 2),
        "units": float(units or 0),
        "by_store": by_store,
    }


def get_category_performance(db: Session, category_name: str, date_range: Any = "this_month") -> dict:
    p = resolve_period(date_range)
    cat = db.scalar(select(Category).where(func.lower(Category.name) == category_name.lower()))
    if not cat:
        return {"category": category_name, "found": False}
    q = (
        select(func.sum(Sale.net_sales), func.sum(Sale.quantity))
        .join(Item, Item.id == Sale.item_id)
        .where(Item.category_id == cat.id, Sale.date >= p.start, Sale.date <= p.end)
    )
    total, units = db.execute(q).one()
    return {
        "category": cat.name,
        "found": True,
        "period_label": p.label,
        "net_sales": round(float(total or 0), 2),
        "units": float(units or 0),
    }


def get_item_performance(db: Session, item_or_barcode: str, date_range: Any = "this_month") -> dict:
    p = resolve_period(date_range)
    item = db.scalar(
        select(Item).where(
            (Item.item_code == item_or_barcode) | (Item.barcode == item_or_barcode)
        )
    )
    if not item:
        return {"found": False, "query": item_or_barcode}
    by_store_q = (
        select(Store.store_code, Store.store_name,
               func.sum(Sale.net_sales), func.sum(Sale.quantity))
        .join(Store, Store.id == Sale.store_id)
        .where(Sale.item_id == item.id, Sale.date >= p.start, Sale.date <= p.end)
        .group_by(Store.store_code, Store.store_name)
        .order_by(func.sum(Sale.net_sales).desc())
    )
    by_store = [
        {"store_code": c, "store_name": n,
         "net_sales": round(float(v or 0), 2), "units": float(u or 0)}
        for c, n, v, u in db.execute(by_store_q).all()
    ]
    total = sum(r["net_sales"] for r in by_store)
    units = sum(r["units"] for r in by_store)
    return {
        "found": True,
        "item_code": item.item_code,
        "barcode": item.barcode,
        "item_name": item.item_name,
        "brand": item.brand.name if item.brand else None,
        "period_label": p.label,
        "total_net_sales": round(total, 2),
        "total_units": units,
        "by_store": by_store,
    }


def compare_brands(
    db: Session,
    brand_a: str,
    brand_b: str,
    date_range: Any = "this_month",
    group_by: str = "store",
) -> dict:
    a = get_brand_performance(db, brand_a, date_range)
    b = get_brand_performance(db, brand_b, date_range)

    head_to_head = []
    if group_by == "store":
        stores = {row["store_code"]: row for row in a.get("by_store", [])}
        for rb in b.get("by_store", []):
            ra = stores.get(rb["store_code"])
            head_to_head.append({
                "store_code": rb["store_code"],
                "store_name": rb["store_name"],
                "store_type": rb.get("store_type"),
                "a": ra["net_sales"] if ra else 0.0,
                "b": rb["net_sales"],
                "winner": brand_a if (ra and ra["net_sales"] > rb["net_sales"]) else brand_b,
            })
        for ra in a.get("by_store", []):
            if ra["store_code"] not in {x["store_code"] for x in head_to_head}:
                head_to_head.append({
                    "store_code": ra["store_code"],
                    "store_name": ra["store_name"],
                    "store_type": ra.get("store_type"),
                    "a": ra["net_sales"],
                    "b": 0.0,
                    "winner": brand_a,
                })

    insight = _brand_insight(a, b, head_to_head)
    return {
        "brand_a": brand_a,
        "brand_b": brand_b,
        "period_label": a.get("period_label"),
        "a": {"net_sales": a.get("net_sales", 0), "units": a.get("units", 0),
              "by_store": a.get("by_store", [])},
        "b": {"net_sales": b.get("net_sales", 0), "units": b.get("units", 0),
              "by_store": b.get("by_store", [])},
        "head_to_head": head_to_head,
        "insight": insight,
    }


def _brand_insight(a: dict, b: dict, head_to_head: list[dict]) -> str:
    if not a.get("found") and not b.get("found"):
        return "No sales data found for either brand in this period."
    a_value = float(a.get("net_sales") or 0)
    b_value = float(b.get("net_sales") or 0)
    leader = a["brand"] if a_value > b_value else b["brand"]
    a_value_stores = sum(1 for r in head_to_head if r["winner"] == a.get("brand") and r.get("store_type") in {"value", "outlet"})
    b_value_stores = sum(1 for r in head_to_head if r["winner"] == b.get("brand") and r.get("store_type") in {"flagship", "general"})
    bits = [f"{leader} leads chain-wide on net sales."]
    if a_value_stores >= 2:
        bits.append(f"{a['brand']} dominates value/outlet stores.")
    if b_value_stores >= 2:
        bits.append(f"{b['brand']} dominates flagship/general stores.")
    return " ".join(bits)


def compare_periods(
    db: Session,
    current_period: Any,
    previous_period: Any,
    store_ids: list[int] | None = None,
) -> dict:
    a = get_sales_summary(db, current_period, store_ids=store_ids)
    b = get_sales_summary(db, previous_period, store_ids=store_ids)
    return {
        "current": a,
        "previous": b,
        "delta_pct": _pct(a["net_sales"], b["net_sales"]),
        "delta_abs": round(a["net_sales"] - b["net_sales"], 2),
    }
