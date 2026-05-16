"""Auto-update policy for email-driven shipment updates.

Per the product spec:
  - SAFE writes (auto-applied): adding a value where there was none, adding
    a new container, adding documents/notes.
  - RISKY writes (flag for review, alert): replacing an existing non-empty
    value with a different value — especially for ETA (>3 days), container
    numbers, booking, BOL, or significant changes to cartons/CBM/weight.
  - DELAY: any new delay creates an alert and is flagged regardless.

This module is the *only* place that writes shipment fields from email data.
Manual writes (PUT /shipments/{id}) still go through shipment_service.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

from ..models import EmailUpdate, Shipment, Container
from . import event_service, alert_service, category_service

log = logging.getLogger("apply")

# Significant change threshold for numeric quantities (cartons / cbm / weight)
QUANTITY_CHANGE_PCT_THRESHOLD = 0.10  # 10%
ETA_DELTA_DAYS_THRESHOLD = 3


# Fields on Shipment that can be safely overwritten when current value is empty.
# Risky overwrites (non-empty → different value) are evaluated per field.
SHIPMENT_SAFE_FIELDS = [
    ("eta_israel",     "date"),
    ("eta_warehouse",  "date"),
    ("eta_port",       "date"),
    ("etd",            "date"),
    ("booking_number", "id"),
    ("bol_number",     "id"),
    ("invoice_number", "id"),
    ("po_number",      "id"),
    ("supplier",       "string"),
    ("customs_broker", "string"),
]

# Container-level fields that can be filled when empty
CONTAINER_FILL_FIELDS = [
    ("cbm",             "quantity"),
    ("boxes_total",     "quantity"),
    ("gross_weight_kg", "quantity"),
    ("container_type",  "string"),
]


@dataclass
class FieldChange:
    entity: str          # 'shipment' / 'container'
    entity_id: int
    field: str
    old_value: Any
    new_value: Any
    decision: str        # 'safe' / 'risky' / 'noop'
    reason: Optional[str] = None


@dataclass
class ApplyResult:
    applied: List[FieldChange] = field(default_factory=list)
    flagged: List[FieldChange] = field(default_factory=list)
    added_containers: List[str] = field(default_factory=list)
    container_conflicts: List[str] = field(default_factory=list)  # container exists in OTHER shipment
    delay_detected: bool = False
    review_reasons: List[str] = field(default_factory=list)

    def to_jsonable(self) -> Dict[str, Any]:
        def _ser(v):
            if isinstance(v, (date, datetime)):
                return v.isoformat()
            return v

        def _change(c: FieldChange):
            return {
                "entity": c.entity, "entity_id": c.entity_id,
                "field": c.field,
                "old_value": _ser(c.old_value), "new_value": _ser(c.new_value),
                "decision": c.decision, "reason": c.reason,
            }
        return {
            "applied": [_change(c) for c in self.applied],
            "flagged": [_change(c) for c in self.flagged],
            "added_containers": self.added_containers,
            "container_conflicts": self.container_conflicts,
            "delay_detected": self.delay_detected,
            "review_reasons": self.review_reasons,
        }

    @property
    def needs_review(self) -> bool:
        return bool(self.flagged or self.delay_detected or self.container_conflicts)


# =====================================================================
# Per-field decision
# =====================================================================

def _is_empty(v: Any) -> bool:
    if v is None:
        return True
    if isinstance(v, str) and not v.strip():
        return True
    if isinstance(v, (int, float)) and v == 0:
        return True
    return False


def _decide_field_change(field_name: str, kind: str, old: Any, new: Any) -> Tuple[str, Optional[str]]:
    """Returns (decision, reason).
    decision ∈ {'safe', 'risky', 'noop'}
    """
    if new is None:
        return "noop", None
    if _is_empty(old):
        return "safe", None
    if old == new:
        return "noop", None

    # Both non-empty and different → evaluate by kind
    if kind == "date":
        try:
            delta = abs((new - old).days)
        except Exception:
            return "risky", f"שינוי תאריך לא ניתן לחישוב: {old} → {new}"
        if delta > ETA_DELTA_DAYS_THRESHOLD:
            return "risky", f"{field_name} זז ב-{delta} ימים: {old} → {new}"
        return "safe", None

    if kind == "id":
        return "risky", f"{field_name} השתנה: {old} → {new}"

    if kind == "quantity":
        try:
            base = max(abs(float(old)), 0.001)
            pct = abs(float(new) - float(old)) / base
        except Exception:
            return "risky", f"שינוי כמות לא ניתן לחישוב: {old} → {new}"
        if pct > QUANTITY_CHANGE_PCT_THRESHOLD:
            return "risky", f"{field_name} השתנה ב-{int(pct*100)}%: {old} → {new}"
        return "safe", None

    if kind == "string":
        # short strings — significant change
        return "risky", f"{field_name} שונה: {old!r} → {new!r}"

    return "risky", f"{field_name}: {old!r} → {new!r}"


# =====================================================================
# Helpers to extract the new ParsedResult shape from EU
# =====================================================================

def _parsed_fields(eu: EmailUpdate) -> Dict[str, Any]:
    raw = eu.detected_fields_json or {}
    if isinstance(raw, dict) and "extracted_fields" in raw:
        return raw["extracted_fields"] or {}
    return raw if isinstance(raw, dict) else {}


def _coerce_date(v) -> Optional[date]:
    if v is None:
        return None
    if isinstance(v, date) and not isinstance(v, datetime):
        return v
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, str):
        try:
            return date.fromisoformat(v)
        except Exception:
            return None
    return None


# =====================================================================
# Main entrypoint
# =====================================================================

def apply_email_to_shipment(
    db: Session,
    eu: EmailUpdate,
    shipment: Shipment,
    *,
    actor: str = "system",
) -> ApplyResult:
    """Apply the email's detected fields to the matched shipment, deciding
    per-field whether to auto-write or flag for review.

    Caller is responsible for db.commit().
    """
    fields = _parsed_fields(eu)
    result = ApplyResult()

    if not fields:
        return result

    # ---- Shipment-level fields ----
    # Map detected names → shipment column names (handle bl_number alias)
    field_map = {
        "eta_israel":     "eta_israel",
        "eta_warehouse":  "eta_warehouse",
        "eta_port":       "eta_port",
        "etd":            "etd",
        "booking_number": "booking_number",
        "bl_number":      "bol_number",      # detected name → column name
        "invoice_number": "invoice_number",
        "po_number":      "po_number",
        "supplier":       "supplier",
    }
    kind_map = {f: k for f, k in SHIPMENT_SAFE_FIELDS}
    kind_map["bol_number"] = "id"

    shp_overrides = shipment.manual_overrides or {}
    for det_name, col in field_map.items():
        if det_name not in fields:
            continue
        new_val = fields[det_name]
        if col in ("eta_israel", "eta_warehouse", "eta_port", "etd"):
            new_val = _coerce_date(new_val)
            if new_val is None:
                continue
        old_val = getattr(shipment, col, None)
        decision, reason = _decide_field_change(col, kind_map.get(col, "string"), old_val, new_val)

        # Manual-override sticky rule: if a user manually edited this field,
        # NEVER auto-overwrite — flag for review with a clear reason.
        override = shp_overrides.get(col) if old_val != new_val else None
        if override and decision != "noop":
            who = override.get("by") or "user"
            decision = "risky"
            reason = f"השדה {col} נערך ידנית ע״י {who} — לא נדרס אוטומטית"

        change = FieldChange(
            entity="shipment", entity_id=shipment.id, field=col,
            old_value=old_val, new_value=new_val,
            decision=decision, reason=reason,
        )
        if decision == "safe":
            setattr(shipment, col, new_val)
            result.applied.append(change)
            event_service.log_event(
                db,
                entity_type="shipment", entity_id=shipment.id,
                action_type="auto_update", field_changed=col,
                old_value=old_val, new_value=new_val,
                changed_by=actor, source="email_auto",
                note=f"מתוך מייל #{eu.id}",
            )
        elif decision == "risky":
            result.flagged.append(change)
            if reason:
                result.review_reasons.append(reason)
        # noop → ignore

    # ---- Container number additions ----
    detected_containers: List[str] = fields.get("container_numbers") or []
    existing_in_shipment = {c.container_number for c in shipment.containers if c.container_number}
    for cn in detected_containers:
        if cn in existing_in_shipment:
            continue
        # Check if this container number exists in a DIFFERENT shipment
        other = (
            db.query(Container)
            .filter(Container.container_number == cn,
                    Container.shipment_id != shipment.id)
            .first()
        )
        if other:
            other_ship = db.query(Shipment).filter(Shipment.id == other.shipment_id).first()
            other_label = other_ship.shp_id if other_ship else f"shipment#{other.shipment_id}"
            result.container_conflicts.append(cn)
            result.review_reasons.append(
                f"מכולה {cn} כבר משויכת ל-{other_label}"
            )
            continue
        # Add as new container
        new_c = Container(
            shipment_id=shipment.id,
            container_number=cn,
            container_status="זוהה במייל",
            unloading_priority="רגיל",
            extra_work_required=False,
            updated_by=actor,
        )
        db.add(new_c)
        db.flush()
        result.added_containers.append(cn)
        event_service.log_event(
            db,
            entity_type="container", entity_id=new_c.id,
            action_type="auto_create", new_value=cn,
            changed_by=actor, source="email_auto",
            note=f"נוספה אוטומטית ממייל #{eu.id}",
        )

    # ---- Container-level metrics (cbm, weight, cartons) ----
    # Apply only when the email's detected_container_id is set (we know which
    # container it refers to). Otherwise skip — too ambiguous to auto-apply.
    if eu.detected_container_id:
        target_c = db.query(Container).filter(
            Container.id == eu.detected_container_id
        ).first()
        if target_c:
            cont_overrides = target_c.manual_overrides or {}
            metric_map = {
                "cbm":       "cbm",
                "weight_kg": "gross_weight_kg",
                "cartons":   "boxes_total",
            }
            for det_name, col in metric_map.items():
                if det_name not in fields:
                    continue
                new_val = fields[det_name]
                old_val = getattr(target_c, col, None)
                decision, reason = _decide_field_change(col, "quantity", old_val, new_val)
                # Manual-override sticky rule for container metrics
                override = cont_overrides.get(col) if old_val != new_val else None
                if override and decision != "noop":
                    who = override.get("by") or "user"
                    decision = "risky"
                    reason = f"השדה {col} נערך ידנית ע״י {who} — לא נדרס אוטומטית"
                change = FieldChange(
                    entity="container", entity_id=target_c.id, field=col,
                    old_value=old_val, new_value=new_val,
                    decision=decision, reason=reason,
                )
                if decision == "safe":
                    setattr(target_c, col, new_val)
                    result.applied.append(change)
                    event_service.log_event(
                        db,
                        entity_type="container", entity_id=target_c.id,
                        action_type="auto_update", field_changed=col,
                        old_value=old_val, new_value=new_val,
                        changed_by=actor, source="email_auto",
                        note=f"מתוך מייל #{eu.id}",
                    )
                elif decision == "risky":
                    result.flagged.append(change)
                    if reason:
                        result.review_reasons.append(reason)

    # ---- Category detection ----
    # Detect from subject + body + goods_description + supplier
    detected_category = category_service.detect_category(
        eu.subject, eu.full_body_text or eu.body_excerpt,
        shipment.goods_description, shipment.supplier,
    )
    if detected_category:
        if not shipment.category:
            # Empty → auto-fill (safe)
            old = shipment.category
            shipment.category = detected_category
            shipment.category_source = "email_auto"
            result.applied.append(FieldChange(
                entity="shipment", entity_id=shipment.id, field="category",
                old_value=old, new_value=detected_category,
                decision="safe",
            ))
            event_service.log_event(
                db,
                entity_type="shipment", entity_id=shipment.id,
                action_type="auto_update", field_changed="category",
                old_value=old, new_value=detected_category,
                changed_by=actor, source="email_auto",
                note=f"זוהתה קטגוריה אוטומטית ממייל #{eu.id}",
            )
        elif shipment.category != detected_category:
            # Conflict — don't overwrite, flag
            change = FieldChange(
                entity="shipment", entity_id=shipment.id, field="category",
                old_value=shipment.category, new_value=detected_category,
                decision="risky",
                reason=f"קטגוריה שונה: {shipment.category} → {detected_category}",
            )
            result.flagged.append(change)
            result.review_reasons.append(
                f"קטגוריה במייל ({detected_category}) שונה מהקיימת ({shipment.category})"
            )

    # ---- Delay detection — always alert + flag ----
    if fields.get("delay_detected"):
        result.delay_detected = True
        result.review_reasons.append("זוהה עיכוב במייל — דורש בדיקה ומענה")
        alert_service.create_alert(
            db,
            alert_type="delay_detected_in_email",
            title=f"זוהה עיכוב — {shipment.shp_id}",
            description=(eu.subject or "")[:200],
            severity="high",
            shipment_id=shipment.id,
            email_update_id=eu.id,
        )
        # Also flip shipment.delay_status if it wasn't True (safe upgrade —
        # but the delay_reason is human-text so we leave it for the user)
        if not shipment.delay_status:
            shipment.delay_status = True
            shipment.delay_reason = shipment.delay_reason or "זוהה במייל — דורש פירוט"
            event_service.log_event(
                db,
                entity_type="shipment", entity_id=shipment.id,
                action_type="auto_update", field_changed="delay_status",
                old_value=False, new_value=True,
                changed_by=actor, source="email_auto",
                note=f"זיהוי עיכוב במייל #{eu.id}",
            )

    # ---- Bookkeeping on the shipment + email ----
    if result.applied or result.added_containers:
        shipment.last_auto_update_source_email_id = eu.id
        shipment.last_auto_update_at = datetime.utcnow()

    eu.applied_fields_json = [
        {"entity": c.entity, "field": c.field, "old": str(c.old_value or ""), "new": str(c.new_value or "")}
        for c in result.applied
    ] + [
        {"entity": "container", "field": "container_number", "old": "", "new": cn}
        for cn in result.added_containers
    ]
    eu.flagged_fields_json = [
        {"entity": c.entity, "field": c.field,
         "old": str(c.old_value or ""), "new": str(c.new_value or ""),
         "reason": c.reason}
        for c in result.flagged
    ] + [
        {"entity": "container", "field": "container_number", "new": cn,
         "reason": "מכולה כבר משויכת למשלוח אחר"}
        for cn in result.container_conflicts
    ]
    eu.auto_applied = bool(result.applied or result.added_containers) and not result.needs_review
    eu.needs_review = result.needs_review
    if result.review_reasons:
        eu.review_reason = " · ".join(result.review_reasons)

    db.flush()

    # ---- Single alert for non-delay risky changes ----
    if result.flagged or result.container_conflicts:
        alert_service.create_alert(
            db,
            alert_type="email_update_needs_review",
            title=f"עדכון מייל דורש בדיקה — {shipment.shp_id}",
            description=" · ".join(result.review_reasons[:5]),
            severity="high",
            shipment_id=shipment.id,
            email_update_id=eu.id,
        )

    log.info(
        "EU#%s apply: shp=%s applied=%d flagged=%d added_containers=%d delay=%s review=%s",
        eu.id, shipment.shp_id,
        len(result.applied), len(result.flagged),
        len(result.added_containers), result.delay_detected,
        result.needs_review,
    )

    return result
