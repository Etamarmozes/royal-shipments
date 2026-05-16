"""Warehouse AI Assistant — answers questions strictly from the database.

Hard rules:
- No LLM. No external calls. No hallucinations.
- Pattern-match the user's question to a fixed set of intents and run
  deterministic SQL queries against the data we already have.
- Every answer cites its sources (Shipment / Container / Document / Email).
- If we can't find the data, say so clearly. Never invent.

Two modes share this single entry point:
- Management mode (no context) — questions like "what arrives this week",
  "categories arriving this month".
- Warehouse mode (context.container_id or container number in question) —
  questions like "what's supposed to be in this container", "how many
  cartons are expected", "which documents are missing".

The caller passes optional context:
    {"container_id": int, "shipment_id": int, "page": "receiving"}

The handler also extracts any container number / SHP-ID written directly
in the user's question, and gives those priority over context.
"""
from __future__ import annotations

import logging
import re
from datetime import date, timedelta
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Callable, Tuple
from sqlalchemy.orm import Session, joinedload

from ..models import (
    Shipment, Container, EmailAttachment, EmailUpdate, Alert, ShipmentEvent,
)
from . import category_service, document_service

log = logging.getLogger("ai")


# =====================================================================
# Result types
# =====================================================================

@dataclass
class AnswerSource:
    kind: str           # 'shipment' / 'container' / 'document' / 'email_update' / 'alert'
    id: int
    label: str
    link: Optional[str] = None


@dataclass
class Answer:
    answer: str
    sources: List[AnswerSource] = field(default_factory=list)
    confidence: str = "high"   # high / medium / low
    intent: str = ""
    actions: List[Dict[str, str]] = field(default_factory=list)  # [{label, link}]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "answer": self.answer,
            "intent": self.intent,
            "confidence": self.confidence,
            "sources": [asdict(s) for s in self.sources],
            "actions": self.actions,
        }


# =====================================================================
# Helpers
# =====================================================================

CONTAINER_NUM_RX = re.compile(r"\b([A-Z]{4}\d{7})\b")
SHP_ID_RX = re.compile(r"\bSHP[-\s]?(\d{3,})\b", re.IGNORECASE)

DOC_LABEL = {
    "packing_list": "Packing List", "invoice": "Invoice",
    "bl": "BL", "bol": "BOL",
    "booking_confirmation": "Booking Confirmation",
    "customs": "Customs", "other": "אחר",
}


def _find_container_in_text(db: Session, q: str) -> Optional[Container]:
    m = CONTAINER_NUM_RX.search(q.upper())
    if not m:
        return None
    cn = m.group(1)
    return db.query(Container).filter(Container.container_number == cn).first()


def _find_shipment_in_text(db: Session, q: str) -> Optional[Shipment]:
    m = SHP_ID_RX.search(q)
    if not m:
        return None
    shp = f"SHP-{m.group(1).zfill(3)}"
    return db.query(Shipment).filter(Shipment.shp_id == shp).first()


def _resolve_focus(db: Session, q: str, ctx: Dict[str, Any]) -> Tuple[Optional[Container], Optional[Shipment]]:
    """Decide which container/shipment the user is asking about.
    Question text wins over context."""
    c = _find_container_in_text(db, q)
    s = _find_shipment_in_text(db, q)

    if not c and ctx.get("container_id"):
        c = db.query(Container).filter(Container.id == int(ctx["container_id"])).first()
    if not s and ctx.get("shipment_id"):
        s = db.query(Shipment).filter(Shipment.id == int(ctx["shipment_id"])).first()
    # Auto-fill shipment from container
    if c and not s:
        s = db.query(Shipment).filter(Shipment.id == c.shipment_id).first()
    return c, s


def _effective_eta(c: Container) -> Optional[date]:
    return c.eta_warehouse or c.eta_israel or (c.shipment.eta_warehouse if c.shipment else None) \
        or (c.shipment.eta_israel if c.shipment else None)


def _ship_label(s: Shipment) -> str:
    return f"{s.shp_id} • {s.supplier or '?'}"


def _container_label(c: Container) -> str:
    return c.container_number or f"#{c.id}"


def _docs_for(db: Session, shipment_id: int, container_id: Optional[int] = None) -> List[EmailAttachment]:
    q = db.query(EmailAttachment).filter(EmailAttachment.linked_shipment_id == shipment_id)
    rows = q.all()
    if container_id is not None:
        # Prefer container-specific, but include shipment-level too
        rows.extend(
            db.query(EmailAttachment)
            .filter(EmailAttachment.linked_container_id == container_id,
                    EmailAttachment.linked_shipment_id != shipment_id)
            .all()
        )
    return rows


def _missing_required_docs(rows: List[EmailAttachment]) -> List[str]:
    present = {r.document_type for r in rows if r.document_type}
    if "bol" in present: present.add("bl")
    if "bl" in present: present.add("bol")
    if "booking_confirmation" in present: present.add("bl")
    return [t for t in ("packing_list", "invoice", "bl") if t not in present]


def _week_range(today: date) -> Tuple[date, date]:
    weekday = (today.weekday() + 1) % 7
    sunday = today - timedelta(days=weekday)
    return sunday, sunday + timedelta(days=6)


# =====================================================================
# WAREHOUSE INTENTS — context-aware (focus on a specific container/shipment)
# =====================================================================

def _intent_w_container_contents(db: Session, q: str, c: Optional[Container], s: Optional[Shipment]) -> Answer:
    """'What's supposed to be in this container?' — full overview."""
    if not c and not s:
        return Answer(
            answer="לא הצלחתי לזהות מכולה או משלוח בשאלה. ציין מספר מכולה (כמו MSNU5649034) או SHP.",
            confidence="low", intent="warehouse_container_contents",
        )

    sources: List[AnswerSource] = []
    if c:
        sources.append(AnswerSource("container", c.id, _container_label(c),
                                    link=f"/containers/{c.id}"))
    if s:
        sources.append(AnswerSource("shipment", s.id, _ship_label(s),
                                    link=f"/shipments/{s.id}"))

    parts: List[str] = []
    if c:
        parts.append(
            f"במכולה {c.container_number or f'#{c.id}'} אמור להגיע משלוח "
            f"{s.shp_id if s else '(לא משויך)'}{' של ' + s.supplier if s and s.supplier else ''}."
        )
    elif s:
        parts.append(f"משלוח {s.shp_id} של {s.supplier or 'ספק לא ידוע'}.")

    if s and s.goods_description:
        parts.append(f"המוצר: {s.goods_description}.")
    elif s:
        parts.append("⚠ אין במערכת תיאור מוצר.")

    cat = (c.category if c else None) or (s.category if s else None)
    if cat:
        parts.append(f"קטגוריה: {cat}.")

    if c:
        if c.boxes_total:
            parts.append(f"כמות צפויה: {c.boxes_total} קרטונים.")
        else:
            parts.append("⚠ כמות קרטונים לא הוזנה.")
        if c.estimated_pallets_final:
            parts.append(f"משטחים צפויים: {c.estimated_pallets_final}.")
        if c.cbm:
            parts.append(f"CBM: {c.cbm}.")
        if c.gross_weight_kg:
            parts.append(f"משקל ברוטו: {int(c.gross_weight_kg)} ק״ג.")

    eta = _effective_eta(c) if c else (s.eta_warehouse or s.eta_israel if s else None)
    if eta:
        parts.append(f"ETA: {eta.isoformat()}.")
    else:
        parts.append("⚠ אין ETA במערכת.")

    if s and s.delay_status:
        parts.append(f"⚠ המשלוח מסומן בעיכוב{(' — ' + s.delay_reason) if s.delay_reason else ''}.")

    # Document presence
    if s:
        docs = _docs_for(db, s.id, c.id if c else None)
        present = {d.document_type for d in docs if d.document_type}
        if "bol" in present: present.add("bl")
        if "booking_confirmation" in present: present.add("bl")
        miss = _missing_required_docs(docs)
        for t in ("packing_list", "invoice", "bl"):
            label = DOC_LABEL[t]
            if t in present:
                parts.append(f"{label} קיים.")
            else:
                parts.append(f"⚠ {label} עדיין חסר.")
        for d in docs:
            sources.append(AnswerSource(
                "document", d.id,
                f"{DOC_LABEL.get(d.document_type or 'other', d.document_type or 'doc')} • {d.filename or ''}",
                link="/documents",
            ))

    # Receiving status
    if c:
        if c.receiving_status and c.receiving_status != "not_received":
            actual = []
            if c.received_cartons_actual is not None:
                actual.append(f"{c.received_cartons_actual} קרטונים")
            if c.received_pallets_actual is not None:
                actual.append(f"{c.received_pallets_actual} משטחים")
            parts.append(
                f"סטטוס קליטה: {c.receiving_status}"
                + (f" — נקלטו: {', '.join(actual)}" if actual else "")
                + "."
            )

    actions = []
    if c:
        actions.append({"label": "פתח מכולה", "link": f"/containers/{c.id}"})
        actions.append({"label": "מעבר לקליטה", "link": f"/receiving?container={c.id}"})
    if s:
        actions.append({"label": "פתח משלוח", "link": f"/shipments/{s.id}"})

    return Answer(
        answer=" ".join(parts),
        sources=sources, actions=actions,
        intent="warehouse_container_contents",
    )


def _intent_w_quantities(db: Session, q: str, c: Optional[Container], s: Optional[Shipment]) -> Answer:
    if not c:
        if not s:
            return Answer(
                answer="ציין מספר מכולה כדי לדעת כמה קרטונים/משטחים צפויים.",
                confidence="low", intent="warehouse_expected_quantities",
            )
        # shipment-level summary
        cs = db.query(Container).filter(Container.shipment_id == s.id).all()
        total_cart = sum(c2.boxes_total or 0 for c2 in cs)
        total_pal = sum(c2.estimated_pallets_final or 0 for c2 in cs)
        return Answer(
            answer=(
                f"במשלוח {s.shp_id} יש {len(cs)} מכולות, סה\"כ {total_cart} קרטונים "
                f"ו-{total_pal} משטחים צפויים."
            ),
            sources=[AnswerSource("shipment", s.id, _ship_label(s), f"/shipments/{s.id}")],
            intent="warehouse_expected_quantities",
        )

    parts: List[str] = []
    if c.boxes_total:
        parts.append(f"קרטונים צפויים: {c.boxes_total}")
    else:
        parts.append("⚠ כמות קרטונים לא הוזנה במערכת")
    if c.estimated_pallets_final:
        parts.append(f"משטחים צפויים: {c.estimated_pallets_final}")
    else:
        parts.append("⚠ אין חישוב משטחים")
    if c.cbm:
        parts.append(f"CBM: {c.cbm}")
    if c.gross_weight_kg:
        parts.append(f"משקל: {int(c.gross_weight_kg)} ק״ג")

    return Answer(
        answer=f"במכולה {c.container_number}: " + " · ".join(parts) + ".",
        sources=[AnswerSource("container", c.id, _container_label(c), f"/containers/{c.id}")],
        actions=[{"label": "פתח מכולה", "link": f"/containers/{c.id}"}],
        intent="warehouse_expected_quantities",
    )


def _intent_w_documents(db: Session, q: str, c: Optional[Container], s: Optional[Shipment]) -> Answer:
    if not s and c:
        s = db.query(Shipment).filter(Shipment.id == c.shipment_id).first()
    if not s:
        return Answer(
            answer="ציין מכולה או משלוח כדי לראות אילו מסמכים מצורפים.",
            confidence="low", intent="warehouse_document_lookup",
        )

    docs = _docs_for(db, s.id, c.id if c else None)
    if not docs:
        return Answer(
            answer=f"לא מצאתי שום מסמך מצורף ל-{s.shp_id}. גם Packing List, גם Invoice, גם BL — חסרים.",
            sources=[AnswerSource("shipment", s.id, _ship_label(s), f"/shipments/{s.id}")],
            actions=[{"label": "פתח מסמכי המשלוח", "link": "/documents"}],
            intent="warehouse_document_lookup",
            confidence="medium",
        )

    by_type: Dict[str, List[EmailAttachment]] = {}
    for d in docs:
        by_type.setdefault(d.document_type or "other", []).append(d)

    lines = [f"ב-{s.shp_id} מצאתי {len(docs)} מסמכים:"]
    for t, ds in by_type.items():
        lines.append(f"  • {DOC_LABEL.get(t, t)}: {len(ds)} ({', '.join(d.filename or '?' for d in ds)})")
    miss = _missing_required_docs(docs)
    if miss:
        lines.append("חסר עדיין: " + ", ".join(DOC_LABEL[t] for t in miss))

    return Answer(
        answer="\n".join(lines),
        sources=[
            AnswerSource("document", d.id,
                         f"{DOC_LABEL.get(d.document_type or 'other', '?')} • {d.filename or ''}",
                         "/documents")
            for d in docs
        ],
        actions=[{"label": "פתח כל המסמכים", "link": "/documents"}],
        intent="warehouse_document_lookup",
    )


def _intent_w_receiving_check(db: Session, q: str, c: Optional[Container], s: Optional[Shipment]) -> Answer:
    """Pre-flight checklist: can we approve receipt?"""
    if not c:
        return Answer(
            answer="ציין מכולה כדי שאוכל לבדוק אם אפשר לאשר קבלה.",
            confidence="low", intent="warehouse_receiving_check",
        )
    issues: List[str] = []
    blockers: List[str] = []

    if not c.boxes_total:
        blockers.append("כמות קרטונים צפויה לא הוזנה")
    if not s or not s.goods_description:
        issues.append("אין תיאור מוצר")
    docs = _docs_for(db, c.shipment_id, c.id) if s else []
    miss = _missing_required_docs(docs)
    for t in miss:
        issues.append(f"חסר {DOC_LABEL[t]}")
    if c.received_cartons_actual is None and c.received_pallets_actual is None:
        issues.append("עוד לא הוזנה כמות שהתקבלה בפועל")

    if not blockers and not issues:
        return Answer(
            answer=f"✓ הכל תקין למכולה {c.container_number}. אפשר לאשר קבלה.",
            sources=[AnswerSource("container", c.id, _container_label(c), f"/containers/{c.id}")],
            actions=[{"label": "מעבר לקליטה", "link": f"/receiving?container={c.id}"}],
            intent="warehouse_receiving_check",
        )

    msg = []
    if blockers:
        msg.append(f"⛔ חוסמים אישור: {', '.join(blockers)}.")
    if issues:
        msg.append(f"⚠ דורש בדיקה לפני אישור: {', '.join(issues)}.")

    return Answer(
        answer=" ".join(msg),
        sources=[AnswerSource("container", c.id, _container_label(c), f"/containers/{c.id}")],
        actions=[{"label": "מעבר לקליטה", "link": f"/receiving?container={c.id}"}],
        intent="warehouse_receiving_check",
        confidence="high" if blockers else "medium",
    )


def _intent_w_discrepancy(db: Session, q: str, c: Optional[Container], s: Optional[Shipment]) -> Answer:
    if not c:
        return Answer(
            answer="ציין מכולה כדי שאוכל להשוות צפוי מול בפועל.",
            confidence="low", intent="warehouse_discrepancy_check",
        )
    parts: List[str] = []
    if c.received_cartons_actual is None and c.received_pallets_actual is None:
        return Answer(
            answer=f"עדיין לא הוזנו כמויות שהתקבלו במכולה {c.container_number}, אז אין מה להשוות.",
            sources=[AnswerSource("container", c.id, _container_label(c), f"/containers/{c.id}")],
            actions=[{"label": "מעבר לקליטה", "link": f"/receiving?container={c.id}"}],
            intent="warehouse_discrepancy_check",
            confidence="medium",
        )

    if c.boxes_total and c.received_cartons_actual is not None:
        diff = c.received_cartons_actual - c.boxes_total
        if diff == 0:
            parts.append(f"קרטונים: צפוי {c.boxes_total}, התקבל {c.received_cartons_actual} — תואם.")
        else:
            parts.append(f"⚠ קרטונים: צפוי {c.boxes_total}, התקבל {c.received_cartons_actual} (פער {diff:+d}).")

    if c.estimated_pallets_final and c.received_pallets_actual is not None:
        diff = c.received_pallets_actual - c.estimated_pallets_final
        if diff == 0:
            parts.append(f"משטחים: צפוי {c.estimated_pallets_final}, התקבל {c.received_pallets_actual} — תואם.")
        else:
            parts.append(f"⚠ משטחים: צפוי {c.estimated_pallets_final}, התקבל {c.received_pallets_actual} (פער {diff:+d}).")

    # Was a discrepancy alert created?
    discrepancy_alerts = db.query(Alert).filter(
        Alert.container_id == c.id,
        Alert.alert_type.in_(["receiving_carton_discrepancy", "receiving_pallet_discrepancy"]),
        Alert.resolved == False,  # noqa: E712
    ).all()
    if discrepancy_alerts:
        parts.append(f"קיימות {len(discrepancy_alerts)} התראות פער פתוחות.")

    return Answer(
        answer=" ".join(parts) or "אין מספיק נתונים להשוואה.",
        sources=[AnswerSource("container", c.id, _container_label(c), f"/containers/{c.id}")] + [
            AnswerSource("alert", a.id, a.title, "/alerts") for a in discrepancy_alerts
        ],
        intent="warehouse_discrepancy_check",
        confidence="high" if parts else "low",
    )


def _intent_w_missing_info(db: Session, q: str, c: Optional[Container], s: Optional[Shipment]) -> Answer:
    if not c and not s:
        return Answer(
            answer="ציין מכולה או משלוח כדי שאוכל לסכם מה חסר.",
            confidence="low", intent="warehouse_missing_info",
        )
    missing: List[str] = []
    if c:
        if not c.boxes_total: missing.append("כמות קרטונים")
        if not c.cbm: missing.append("CBM")
        if not c.gross_weight_kg: missing.append("משקל")
        if not c.carton_length_cm: missing.append("מידות קרטון")
        if not _effective_eta(c): missing.append("ETA")
        if not (c.category or (s.category if s else None)): missing.append("קטגוריה")
    if s:
        if not s.goods_description: missing.append("תיאור מוצר")
        docs = _docs_for(db, s.id, c.id if c else None)
        for t in _missing_required_docs(docs):
            missing.append(DOC_LABEL[t])

    if not missing:
        return Answer(
            answer="לא חסר כלום במערכת — כל הנתונים קיימים.",
            sources=[AnswerSource("container", c.id, _container_label(c), f"/containers/{c.id}")] if c else [],
            intent="warehouse_missing_info",
        )

    label = c.container_number if c else (s.shp_id if s else "?")
    return Answer(
        answer=f"חסר ב-{label}: " + ", ".join(missing) + ".",
        sources=[
            AnswerSource("container", c.id, _container_label(c), f"/containers/{c.id}") if c else None,
            AnswerSource("shipment", s.id, _ship_label(s), f"/shipments/{s.id}") if s else None,
        ] if c or s else [],
        intent="warehouse_missing_info",
        confidence="high",
    )


def _intent_w_shipment_linkage(db: Session, q: str, c: Optional[Container], s: Optional[Shipment]) -> Answer:
    if not c and not s:
        return Answer(
            answer="ציין מכולה או משלוח כדי שאוכל לראות את הקשרים.",
            confidence="low", intent="warehouse_shipment_linkage",
        )
    if c and not s:
        s = db.query(Shipment).filter(Shipment.id == c.shipment_id).first()

    if not s:
        return Answer(
            answer=f"⚠ המכולה {c.container_number if c else '?'} לא משויכת לאף משלוח. דורש בדיקה ידנית.",
            sources=[AnswerSource("container", c.id, _container_label(c), f"/containers/{c.id}")] if c else [],
            intent="warehouse_shipment_linkage",
            confidence="medium",
        )

    siblings = db.query(Container).filter(Container.shipment_id == s.id).all()
    sib_lines = [
        f"  • {sc.container_number or '#'+str(sc.id)}"
        + (f" — נקלטה" if sc.receiving_status == "received" else "")
        + (f" — חסרה ETA" if not _effective_eta(sc) else "")
        for sc in siblings
    ]
    answer = (
        f"המכולה{(' ' + c.container_number) if c else ''} שייכת ל-{s.shp_id} ({s.supplier or '?'}).\n"
        f"במשלוח יש {len(siblings)} מכולות:\n" + "\n".join(sib_lines)
    )
    return Answer(
        answer=answer,
        sources=[AnswerSource("shipment", s.id, _ship_label(s), f"/shipments/{s.id}")] + [
            AnswerSource("container", sc.id, _container_label(sc), f"/containers/{sc.id}")
            for sc in siblings
        ],
        intent="warehouse_shipment_linkage",
    )


def _intent_w_eta_status(db: Session, q: str, c: Optional[Container], s: Optional[Shipment]) -> Answer:
    if not c and not s:
        return Answer(
            answer="ציין מכולה או משלוח כדי לבדוק תאריך ועיכובים.",
            confidence="low", intent="warehouse_eta_status",
        )
    target = c.container_number if c else s.shp_id
    eta = _effective_eta(c) if c else (s.eta_warehouse or s.eta_israel if s else None)
    parts = []
    if eta:
        parts.append(f"ETA של {target}: {eta.isoformat()}.")
    else:
        parts.append(f"⚠ אין ETA במערכת ל-{target}.")
    if s and s.delay_status:
        parts.append(
            f"המשלוח מסומן בעיכוב"
            + (f" — סיבה: {s.delay_reason}" if s.delay_reason else "")
            + "."
        )
    # ETA-change events
    sid = (s.id if s else (c.shipment_id if c else None))
    if sid:
        eta_events = db.query(ShipmentEvent).filter(
            ShipmentEvent.entity_type == "shipment",
            ShipmentEvent.entity_id == sid,
            ShipmentEvent.field_changed.in_(["eta_israel", "eta_warehouse", "eta_port"]),
        ).order_by(ShipmentEvent.changed_at.desc()).limit(3).all()
        if eta_events:
            parts.append("שינויי ETA אחרונים:")
            for e in eta_events:
                parts.append(f"  • {e.field_changed}: {e.old_value} → {e.new_value} ({e.source})")
    return Answer(
        answer=" ".join(parts) if parts else "אין מידע.",
        sources=[
            AnswerSource("container", c.id, _container_label(c), f"/containers/{c.id}") if c else None,
            AnswerSource("shipment", s.id, _ship_label(s), f"/shipments/{s.id}") if s else None,
        ] if c or s else [],
        intent="warehouse_eta_status",
    )


# =====================================================================
# GENERAL (management) intents — kept from previous version
# =====================================================================

def _intent_arriving_this_week(db: Session, q: str) -> Answer:
    today = date.today()
    s_start, s_end = _week_range(today)
    rows = db.query(Container).options(joinedload(Container.shipment)).all()
    matches = []
    pallets = 0
    for c in rows:
        eta = c.eta_israel or (c.shipment.eta_israel if c.shipment else None)
        if not eta or not (s_start <= eta <= s_end):
            continue
        if c.shipment and c.shipment.archived:
            continue
        matches.append(c)
        pallets += c.estimated_pallets_final or 0
    if not matches:
        return Answer(answer="אין מכולות שצפויות להגיע השבוע (לפי ETA הקיים במערכת).",
                      intent="arriving_this_week")
    return Answer(
        answer=f"השבוע ({s_start} – {s_end}) צפויות {len(matches)} מכולות, סה\"כ {pallets} משטחים.",
        sources=[AnswerSource("container", c.id, c.container_number or f"#{c.id}",
                              f"/containers/{c.id}") for c in matches],
        intent="arriving_this_week",
    )


def _intent_delayed(db: Session, q: str) -> Answer:
    rows = db.query(Shipment).filter(
        Shipment.delay_status == True, Shipment.archived == False  # noqa: E712
    ).all()
    if not rows:
        return Answer(answer="אין משלוחים בעיכוב כרגע.", intent="delayed")
    return Answer(
        answer=f"{len(rows)} משלוחים בעיכוב: " + ", ".join(s.shp_id for s in rows[:8]) +
               ("…" if len(rows) > 8 else ""),
        sources=[AnswerSource("shipment", s.id, _ship_label(s), f"/shipments/{s.id}") for s in rows],
        intent="delayed",
    )


def _intent_today(db: Session, q: str) -> Answer:
    today = date.today()
    rows = db.query(Container).options(joinedload(Container.shipment)).all()
    matches = [c for c in rows
               if (c.eta_israel or (c.shipment.eta_israel if c.shipment else None)) == today
               and not (c.shipment and c.shipment.archived)]
    if not matches:
        return Answer(answer="אין מכולות שצפויות להגיע היום.", intent="today")
    return Answer(
        answer=f"היום אמורות להגיע {len(matches)} מכולות, "
               f"סה\"כ {sum(c.estimated_pallets_final or 0 for c in matches)} משטחים.",
        sources=[AnswerSource("container", c.id, c.container_number or "?",
                              f"/containers/{c.id}") for c in matches],
        intent="today",
    )


def _intent_categories_month(db: Session, q: str) -> Answer:
    today = date.today()
    end = today + timedelta(days=30)
    rows = db.query(Container).options(joinedload(Container.shipment)).all()
    by_cat: Dict[str, Dict[str, Any]] = {}
    for c in rows:
        if c.shipment and c.shipment.archived:
            continue
        eta = c.eta_israel or (c.shipment.eta_israel if c.shipment else None)
        if not eta or not (today <= eta <= end):
            continue
        cat = c.category or (c.shipment.category if c.shipment else None) or "אחר"
        e = by_cat.setdefault(cat, {"containers": 0, "pallets": 0})
        e["containers"] += 1
        e["pallets"] += c.estimated_pallets_final or 0
    if not by_cat:
        return Answer(answer="לא נמצאו מכולות עם ETA ב-30 הימים הקרובים.",
                      intent="categories_this_month")
    parts = [f"{cat}: {v['containers']} מכולות, {v['pallets']} משטחים" for cat, v in by_cat.items()]
    return Answer(answer="קטגוריות ב-30 ימים הקרובים: " + " · ".join(parts),
                  intent="categories_this_month")


def _intent_supplier(db: Session, q: str) -> Answer:
    m = re.search(r"(?:ספק|supplier|of)\s+([A-Za-zא-ת][A-Za-zא-ת\s\-&\./]{2,40})", q, re.IGNORECASE)
    if not m:
        return Answer(answer="ציין שם ספק לחיפוש.", confidence="low", intent="supplier")
    needle = m.group(1).strip()
    rows = db.query(Shipment).filter(
        Shipment.archived == False,  # noqa: E712
        Shipment.supplier.ilike(f"%{needle}%"),
    ).all()
    if not rows:
        return Answer(answer=f"לא נמצאו משלוחים מהספק '{needle}'.", intent="supplier")
    return Answer(
        answer=f"נמצאו {len(rows)} משלוחים של '{needle}': " + ", ".join(s.shp_id for s in rows[:10]),
        sources=[AnswerSource("shipment", s.id, _ship_label(s), f"/shipments/{s.id}") for s in rows],
        intent="supplier",
    )


def _intent_unknown(db: Session, q: str) -> Answer:
    return Answer(
        answer="לא מצאתי נתון כזה במערכת. אם אתה במחסן, נסה: "
               "'מה אמור להיות במכולה <מס׳>', 'כמה קרטונים צפויים', "
               "'איזה מסמכים חסרים', 'יש פער?', 'אפשר לאשר קבלה?'",
        confidence="low", intent="unknown",
    )


# =====================================================================
# Intent matching
# =====================================================================

# Warehouse intents — preferred when context has a container/shipment focus
WAREHOUSE_INTENTS: List[Tuple[List[str], Callable]] = [
    (["יש פער", "פער", "discrepancy", "תואם", "מה התקבל"], _intent_w_discrepancy),
    (["אפשר לאשר", "אישור קבלה", "מה חסר לפני", "מה חסר לאישור", "approve receipt"],
     _intent_w_receiving_check),
    (["packing list", "פקינג", "פקינג ליסט", "invoice", "חשבונית", "bl", "bol", "מסמכים", "documents"],
     _intent_w_documents),
    (["איזה משלוח", "לאיזה משלוח", "מאיזה משלוח", "אחיות", "כמה מכולות", "linked shipment", "siblings"],
     _intent_w_shipment_linkage),
    (["eta", "תאריך הגעה", "מתי מגיע", "עיכוב", "delayed", "delay"],
     _intent_w_eta_status),
    (["מה חסר", "missing", "מה לא הוזן"], _intent_w_missing_info),
    (["כמה קרטונים", "כמה משטחים", "כמה צפוי", "כמות צפויה", "expected"],
     _intent_w_quantities),
    (["מה אמור", "מה צפוי", "מה במכולה", "מה במשלוח", "מה תוכן", "תוכן",
      "מי הספק", "supplier", "מוצר", "תיאור", "category", "קטגוריה"],
     _intent_w_container_contents),
]

# General intents — fallback when no container/shipment focus
GENERAL_INTENTS: List[Tuple[List[str], Callable]] = [
    (["מה מגיע היום", "מגיע היום", "today", "היום"], _intent_today),
    (["כמה משטחים השבוע", "משטחים השבוע", "השבוע"], _intent_arriving_this_week),
    (["מה מגיע השבוע", "this week", "arriving"], _intent_arriving_this_week),
    (["מתעכב", "delayed", "delay"], _intent_delayed),
    (["איזה קטגוריות", "קטגוריות בדרך", "categories"], _intent_categories_month),
    (["של ספק", "ספק ", "supplier ", "from supplier"], _intent_supplier),
]


def ask(db: Session, question: str, context: Optional[Dict[str, Any]] = None) -> Answer:
    """Top-level entry point.

    Args:
        question: free text from user
        context: optional dict with shipment_id / container_id / page

    Strategy:
        1. Resolve focus (container + shipment) from question text or context.
        2. If we have focus → try warehouse intents first.
        3. Otherwise (or if no warehouse intent matched) → try general intents.
        4. Last resort: 'unknown' (low confidence, never invents).
    """
    if not question or not question.strip():
        return Answer(answer="אין שאלה.", confidence="low", intent="empty")
    context = context or {}
    q_low = question.lower().strip()

    container, shipment = _resolve_focus(db, question, context)

    # If we have focus → warehouse intents first
    if container or shipment or context.get("page") == "receiving":
        for keywords, handler in WAREHOUSE_INTENTS:
            for kw in keywords:
                if kw.lower() in q_low:
                    try:
                        a = handler(db, question, container, shipment)
                        log.info("AI: q=%r ctx=%s → wh.%s | %s", question, context, a.intent, a.answer[:80])
                        return a
                    except Exception as e:
                        log.exception("AI handler %s failed", handler.__name__)
                        return Answer(answer=f"שגיאה בעיבוד: {e}", confidence="low", intent="error")

        # If user is on receiving page but didn't match a keyword, default
        # to "what should be here?"
        if context.get("page") == "receiving" and (container or shipment):
            return _intent_w_container_contents(db, question, container, shipment)

    # General intents (management)
    for keywords, handler in GENERAL_INTENTS:
        for kw in keywords:
            if kw.lower() in q_low:
                try:
                    a = handler(db, question)
                    log.info("AI: q=%r → mgmt.%s | %s", question, a.intent, a.answer[:80])
                    return a
                except Exception as e:
                    log.exception("AI handler %s failed", handler.__name__)
                    return Answer(answer=f"שגיאה בעיבוד: {e}", confidence="low", intent="error")

    return _intent_unknown(db, question)


# =====================================================================
# Suggestions per page
# =====================================================================

GENERAL_SUGGESTIONS = [
    "מה מגיע השבוע?",
    "מה מתעכב?",
    "כמה משטחים מגיעים השבוע?",
    "איזה קטגוריות בדרך החודש?",
    "כמה משטחים של מגבות מגיעים החודש?",
]

WAREHOUSE_SUGGESTIONS = [
    "מה אמור להגיע פה?",
    "כמה קרטונים צפויים?",
    "כמה משטחים צפויים?",
    "איזה מסמכים חסרים?",
    "האם אפשר לאשר קבלה?",
    "האם יש פער בכמויות?",
    "לאיזה משלוח זה שייך?",
    "מה ETA?",
]


def suggestions_for(context: Optional[Dict[str, Any]] = None) -> List[str]:
    if context and (context.get("container_id") or context.get("page") == "receiving"):
        return WAREHOUSE_SUGGESTIONS
    return GENERAL_SUGGESTIONS
