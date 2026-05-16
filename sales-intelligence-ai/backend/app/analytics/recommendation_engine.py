from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from .inventory_analyzer import detect_inventory_risks
from .sales_analyzer import (
    analyze_store_performance,
    get_bottom_items,
    get_sales_summary,
    get_store_ranking,
    get_top_items,
)


def generate_action_plan(db: Session, date_range: Any = "last_30_days", max_actions: int = 10) -> dict:
    risks = detect_inventory_risks(db)
    actions: list[dict] = []

    for r in risks["fast_moving_low_stock"][:5]:
        actions.append({
            "action": "Reorder",
            "target": f"{r['brand'] or ''} {r['item_name']} @ {r['store_name']}".strip(),
            "priority": "high",
            "why": f"Only {r['days_of_cover']}d of cover at current sales velocity ({r['velocity_units_per_day']} units/day).",
            "expected_impact": "Prevents stockout in a top-selling SKU.",
            "confidence": "high",
        })

    by_item: dict[str, list[dict]] = {}
    for r in risks["slow_moving_high_stock"]:
        by_item.setdefault(r["item_code"], []).append(r)
    for item_code, rows in by_item.items():
        if len(rows) >= 2:
            high = max(rows, key=lambda x: x["inventory"])
            low = next((r for r in risks["fast_moving_low_stock"] if r["item_code"] == item_code), None)
            if low:
                actions.append({
                    "action": "Transfer",
                    "target": f"{high['inventory']:.0f} units of {high['item_name']} from {high['store_name']} → {low['store_name']}",
                    "priority": "high",
                    "why": f"{high['store_name']} has {high['inventory']:.0f} units sitting; {low['store_name']} runs out in {low['days_of_cover']}d.",
                    "expected_impact": "Resolves stockout without buying.",
                    "confidence": "high",
                })

    for r in risks["stuck_items"][:3]:
        actions.append({
            "action": "Stop buying",
            "target": f"{r['brand'] or ''} {r['item_name']}".strip(),
            "priority": "medium",
            "why": f"{r['inventory']:.0f} units in stock, zero sales over the last 30 days.",
            "expected_impact": "Frees working capital.",
            "confidence": "medium",
        })

    perf = analyze_store_performance(db, date_range)
    for w in perf.get("weak_stores", [])[:2]:
        actions.append({
            "action": "Investigate weak store",
            "target": w["store_name"],
            "priority": "medium",
            "why": f"Net sales {w['value']:.0f} vs chain median {perf['median']:.0f}.",
            "expected_impact": "Recover lost revenue if root cause is fixable (staffing, display, mix).",
            "confidence": "medium",
        })

    bottom = get_bottom_items(db, date_range, limit=3)
    for r in bottom:
        actions.append({
            "action": "Promote or discontinue",
            "target": f"{r['brand'] or ''} {r['item_name']}".strip(),
            "priority": "low",
            "why": f"Only {r['value']:.0f} ₪ in net sales over the period.",
            "expected_impact": "Either recover with a promo or remove from assortment.",
            "confidence": "low",
        })

    return {"period": date_range, "actions": actions[:max_actions]}


def generate_ceo_summary(db: Session, date_range: Any = "this_month") -> dict:
    summary = get_sales_summary(db, date_range)
    top = get_top_items(db, date_range, limit=3)
    risks = detect_inventory_risks(db)
    ranking = get_store_ranking(db, date_range)
    plan = generate_action_plan(db, date_range, max_actions=3)

    wins: list[str] = []
    if top:
        wins.append(f"Top SKU: {top[0]['item_name']} — {top[0]['value']:,.0f} ₪ ({top[0]['share_pct']}%)")
    if ranking:
        wins.append(f"Top store: {ranking[0]['store_name']} — {ranking[0]['value']:,.0f} ₪")
    if summary["vs_previous_period"]["delta_pct"] is not None and summary["vs_previous_period"]["delta_pct"] > 0:
        wins.append(f"Net sales up {summary['vs_previous_period']['delta_pct']}% vs previous period")

    problems: list[str] = []
    if risks["fast_moving_low_stock"]:
        problems.append(f"{len(risks['fast_moving_low_stock'])} fast-moving SKUs at risk of stockout")
    if risks["slow_moving_high_stock"]:
        problems.append(f"{len(risks['slow_moving_high_stock'])} slow-movers tying up inventory")
    if ranking and len(ranking) > 1 and ranking[-1]["value"] < 0.5 * ranking[0]["value"]:
        problems.append(f"{ranking[-1]['store_name']} underperforming vs chain leader")

    return {
        "period_label": summary["period_label"],
        "headline_metrics": {
            "net_sales": summary["net_sales"],
            "units": summary["units"],
            "vs_prev_pct": summary["vs_previous_period"]["delta_pct"],
        },
        "wins": wins,
        "problems": problems,
        "actions": plan["actions"],
        "watch_this_week": (
            "Inventory cover for top-3 Adidas SKUs in flagship stores"
            if risks["stockout_in_strong_stores"]
            else "Sales pace vs target"
        ),
    }
