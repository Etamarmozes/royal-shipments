from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from .. import analytics
from ..database import get_db

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
def summary(date_range: str = "this_month", db: Session = Depends(get_db)) -> dict:
    return analytics.get_sales_summary(db, date_range=date_range)


@router.get("/top-items")
def top_items(
    date_range: str = "this_month",
    limit: int = 10,
    by: str = "net_sales",
    db: Session = Depends(get_db),
) -> list[dict]:
    return analytics.get_top_items(db, date_range=date_range, limit=limit, by=by)


@router.get("/bottom-items")
def bottom_items(
    date_range: str = "this_month",
    limit: int = 10,
    db: Session = Depends(get_db),
) -> list[dict]:
    return analytics.get_bottom_items(db, date_range=date_range, limit=limit)


@router.get("/stores")
def stores(date_range: str = "this_month", db: Session = Depends(get_db)) -> list[dict]:
    return analytics.get_store_ranking(db, date_range=date_range)


@router.get("/store-performance")
def store_performance(date_range: str = "this_month", db: Session = Depends(get_db)) -> dict:
    return analytics.analyze_store_performance(db, date_range=date_range)


@router.get("/brand")
def brand(name: str = Query(...), date_range: str = "this_month", db: Session = Depends(get_db)) -> dict:
    return analytics.get_brand_performance(db, brand_name=name, date_range=date_range)


@router.get("/compare-brands")
def compare_brands(
    a: str = Query(...),
    b: str = Query(...),
    date_range: str = "this_month",
    db: Session = Depends(get_db),
) -> dict:
    return analytics.compare_brands(db, brand_a=a, brand_b=b, date_range=date_range)


@router.get("/inventory-risks")
def inventory_risks(days_lookback: int = 30, db: Session = Depends(get_db)) -> dict:
    return analytics.detect_inventory_risks(db, days_lookback=days_lookback)


@router.get("/alerts")
def alerts(date_range: str = "last_30_days", db: Session = Depends(get_db)) -> dict:
    """One-stop call for the dashboard alerts strip."""
    plan = analytics.generate_action_plan(db, date_range=date_range, max_actions=10)
    risks = analytics.detect_inventory_risks(db)
    perf = analytics.analyze_store_performance(db, date_range=date_range)
    return {
        "actions": plan["actions"],
        "fast_moving_low_stock_count": len(risks["fast_moving_low_stock"]),
        "slow_moving_high_stock_count": len(risks["slow_moving_high_stock"]),
        "stuck_items_count": len(risks["stuck_items"]),
        "weak_stores": perf["weak_stores"],
    }
