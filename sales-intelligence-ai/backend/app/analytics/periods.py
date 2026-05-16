from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Tuple


@dataclass
class Period:
    start: date
    end: date
    label: str

    def previous(self) -> "Period":
        days = (self.end - self.start).days + 1
        prev_end = self.start - timedelta(days=1)
        prev_start = prev_end - timedelta(days=days - 1)
        return Period(prev_start, prev_end, f"previous {days}d")


def resolve_period(spec, today: date | None = None) -> Period:
    """
    Accepts:
      - "today" / "yesterday" / "this_week" / "last_7_days" / "this_month" /
        "last_30_days" / "last_90_days"
      - {"from": "YYYY-MM-DD", "to": "YYYY-MM-DD"}
    """
    today = today or date.today()
    if isinstance(spec, dict):
        f = date.fromisoformat(spec["from"])
        t = date.fromisoformat(spec["to"])
        return Period(f, t, f"{f} → {t}")

    s = (spec or "this_month").lower()
    if s == "today":
        return Period(today, today, "today")
    if s == "yesterday":
        d = today - timedelta(days=1)
        return Period(d, d, "yesterday")
    if s in {"this_week", "week"}:
        start = today - timedelta(days=today.weekday())
        return Period(start, today, "this week")
    if s in {"last_7_days", "7d"}:
        return Period(today - timedelta(days=6), today, "last 7 days")
    if s in {"this_month", "month", "mtd"}:
        return Period(today.replace(day=1), today, "month-to-date")
    if s in {"last_30_days", "30d"}:
        return Period(today - timedelta(days=29), today, "last 30 days")
    if s in {"last_90_days", "90d"}:
        return Period(today - timedelta(days=89), today, "last 90 days")
    return Period(today.replace(day=1), today, "month-to-date")
