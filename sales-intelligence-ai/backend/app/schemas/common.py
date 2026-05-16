from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ChatRequest(BaseModel):
    question: str


class ChatResponse(BaseModel):
    answer: str
    mode: str
    tool_calls: list[dict[str, Any]] = []


class ReportRequest(BaseModel):
    topic: str  # ceo_summary | brand_comparison | store_ranking | action_plan
    date_range: Any = "this_month"
    format: str = "png"   # png | jpg | pdf
    layout: str = "desktop"
    params: dict[str, Any] = {}


class ImportRunResponse(BaseModel):
    processed: int
    results: list[dict[str, Any]]
