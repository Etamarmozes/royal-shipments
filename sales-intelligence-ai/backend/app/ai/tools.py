"""
Tool definitions for the Anthropic tool-use loop.

Each tool exposes:
  - JSON schema (Anthropic-compatible "input_schema")
  - A Python implementation that runs against SQLite

The model can call these tools but cannot run arbitrary SQL.
"""
from __future__ import annotations

from typing import Any, Callable

from sqlalchemy.orm import Session

from .. import analytics


def _tool(name: str, description: str, input_schema: dict) -> dict:
    return {"name": name, "description": description, "input_schema": input_schema}


PERIOD_SCHEMA = {
    "oneOf": [
        {
            "type": "string",
            "enum": [
                "today", "yesterday", "this_week", "last_7_days",
                "this_month", "last_30_days", "last_90_days",
            ],
        },
        {
            "type": "object",
            "properties": {
                "from": {"type": "string", "format": "date"},
                "to": {"type": "string", "format": "date"},
            },
            "required": ["from", "to"],
        },
    ]
}


TOOL_DEFINITIONS: list[dict] = [
    _tool(
        "get_sales_summary",
        "Top-line sales numbers for a period (gross, net, units, AOV, vs previous period).",
        {
            "type": "object",
            "properties": {
                "date_range": PERIOD_SCHEMA,
                "store_ids": {"type": "array", "items": {"type": "integer"}},
                "brand_ids": {"type": "array", "items": {"type": "integer"}},
                "category_ids": {"type": "array", "items": {"type": "integer"}},
            },
        },
    ),
    _tool(
        "get_top_items",
        "Best-selling items by net sales / units / margin.",
        {
            "type": "object",
            "properties": {
                "date_range": PERIOD_SCHEMA,
                "limit": {"type": "integer", "default": 10},
                "by": {"type": "string", "enum": ["net_sales", "units", "margin"]},
            },
        },
    ),
    _tool(
        "get_bottom_items",
        "Worst-selling items (still with some sales) for the period.",
        {"type": "object", "properties": {"date_range": PERIOD_SCHEMA, "limit": {"type": "integer"}}},
    ),
    _tool(
        "compare_brands",
        "Compare two brands head to head, including per-store breakdown and an automatic insight.",
        {
            "type": "object",
            "properties": {
                "brand_a": {"type": "string"},
                "brand_b": {"type": "string"},
                "date_range": PERIOD_SCHEMA,
                "group_by": {"type": "string", "enum": ["store", "category", "none"]},
            },
            "required": ["brand_a", "brand_b"],
        },
    ),
    _tool(
        "analyze_store_performance",
        "Store ranking, weak stores (sales < 70% of peer median), median.",
        {"type": "object", "properties": {"date_range": PERIOD_SCHEMA}},
    ),
    _tool(
        "get_store_ranking",
        "Stores ordered by net sales, with vs-previous-period delta.",
        {"type": "object", "properties": {"date_range": PERIOD_SCHEMA}},
    ),
    _tool(
        "detect_inventory_risks",
        "Lists of fast-moving low-stock items, slow-moving high-stock items, stuck items, and stockouts in flagship/general stores.",
        {"type": "object", "properties": {"days_lookback": {"type": "integer", "default": 30}}},
    ),
    _tool(
        "get_brand_performance",
        "Sales totals and per-store breakdown for one brand.",
        {
            "type": "object",
            "properties": {"brand": {"type": "string"}, "date_range": PERIOD_SCHEMA},
            "required": ["brand"],
        },
    ),
    _tool(
        "get_category_performance",
        "Sales totals for a category.",
        {
            "type": "object",
            "properties": {"category": {"type": "string"}, "date_range": PERIOD_SCHEMA},
            "required": ["category"],
        },
    ),
    _tool(
        "get_item_performance",
        "Per-store breakdown for a single item by code or barcode.",
        {
            "type": "object",
            "properties": {
                "item_or_barcode": {"type": "string"},
                "date_range": PERIOD_SCHEMA,
            },
            "required": ["item_or_barcode"],
        },
    ),
    _tool(
        "generate_ceo_summary",
        "Wins / problems / 3 recommended actions / what to watch — a CEO-grade brief.",
        {"type": "object", "properties": {"date_range": PERIOD_SCHEMA}},
    ),
    _tool(
        "generate_action_plan",
        "Prioritized list of concrete actions: reorder, transfer, stop-buy, investigate.",
        {
            "type": "object",
            "properties": {"date_range": PERIOD_SCHEMA, "max_actions": {"type": "integer"}},
        },
    ),
]


def _wrap(fn: Callable[..., Any]):
    """Bind the db session to a tool implementation."""
    def adapter(db: Session, **kwargs):
        return fn(db, **kwargs)
    return adapter


TOOL_IMPLS: dict[str, Callable[..., Any]] = {
    "get_sales_summary": _wrap(analytics.get_sales_summary),
    "get_top_items": _wrap(analytics.get_top_items),
    "get_bottom_items": _wrap(analytics.get_bottom_items),
    "compare_brands": _wrap(analytics.compare_brands),
    "analyze_store_performance": _wrap(analytics.analyze_store_performance),
    "get_store_ranking": _wrap(analytics.get_store_ranking),
    "detect_inventory_risks": _wrap(analytics.detect_inventory_risks),
    "get_brand_performance": lambda db, **kw: analytics.get_brand_performance(
        db, brand_name=kw.pop("brand"), **kw),
    "get_category_performance": lambda db, **kw: analytics.get_category_performance(
        db, category_name=kw.pop("category"), **kw),
    "get_item_performance": _wrap(analytics.get_item_performance),
    "generate_ceo_summary": _wrap(analytics.generate_ceo_summary),
    "generate_action_plan": _wrap(analytics.generate_action_plan),
}


def call_tool(db: Session, name: str, args: dict | None) -> Any:
    impl = TOOL_IMPLS.get(name)
    if impl is None:
        return {"error": f"unknown tool: {name}"}
    args = args or {}
    try:
        return impl(db, **args)
    except TypeError as e:
        return {"error": f"bad arguments for {name}: {e}"}
    except Exception as e:
        return {"error": f"{name} failed: {type(e).__name__}: {e}"}
