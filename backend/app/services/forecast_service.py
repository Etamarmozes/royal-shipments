from datetime import date, timedelta
from typing import List, Dict, Any
from sqlalchemy.orm import Session, joinedload

from ..models import Container, Shipment


def load_status_for_count(n: int) -> str:
    if n <= 2:
        return "פנוי"
    if n <= 5:
        return "רגיל"
    if n <= 8:
        return "עמוס"
    return "חריג"


def week_range(week_index: int) -> tuple[date, date]:
    """Week 0 = current week (Sunday-based for Israel)."""
    today = date.today()
    # Sunday=0
    weekday = (today.weekday() + 1) % 7
    sunday = today - timedelta(days=weekday)
    start = sunday + timedelta(days=7 * week_index)
    end = start + timedelta(days=6)
    return start, end


def effective_eta_israel(c: Container, s: Shipment | None) -> date | None:
    return c.eta_israel or (s.eta_israel if s else None)


def forecast_8_weeks(db: Session) -> List[Dict[str, Any]]:
    containers = (
        db.query(Container)
        .options(joinedload(Container.shipment))
        .all()
    )

    weeks: List[Dict[str, Any]] = []
    for i in range(8):
        start, end = week_range(i)
        in_week_israel: List[Container] = []
        in_week_port: List[Container] = []
        in_week_warehouse: List[Container] = []
        suppliers: set[str] = set()
        cbm_total = 0.0
        weight_total = 0.0
        boxes_total = 0
        ids: list[int] = []

        for c in containers:
            s = c.shipment
            eta_il = c.eta_israel or (s.eta_israel if s else None)
            eta_port = c.eta_port or (s.eta_port if s else None)
            eta_wh = c.eta_warehouse or (s.eta_warehouse if s else None)

            if eta_il and start <= eta_il <= end:
                in_week_israel.append(c)
                if s and s.supplier:
                    suppliers.add(s.supplier)
                cbm_total += c.cbm or 0
                weight_total += c.gross_weight_kg or 0
                boxes_total += c.boxes_total or 0
                ids.append(c.id)

            if eta_port and start <= eta_port <= end:
                in_week_port.append(c)
            if eta_wh and start <= eta_wh <= end:
                in_week_warehouse.append(c)

        weeks.append({
            "week_index": i,
            "week_label": f"שבוע {i + 1}",
            "week_start": start,
            "week_end": end,
            "containers_arriving_israel": len(in_week_israel),
            "containers_arriving_port": len(in_week_port),
            "containers_arriving_warehouse": len(in_week_warehouse),
            "cbm_total": round(cbm_total, 2),
            "weight_total_kg": round(weight_total, 2),
            "boxes_total": boxes_total,
            "suppliers": sorted(suppliers),
            "load_status": load_status_for_count(len(in_week_israel)),
            "container_ids": ids,
        })
    return weeks
