"""Document Assignment QC engine.

Audits every linked attachment by scanning real business signals:
  - filename
  - source email subject
  - source email sender (domain especially)
  - source email body (excerpt + full text)
  - PDF-extracted text if available

Each shipment supplier is matched against configurable keyword rules.
The engine produces an `assignment_confidence_score` (0..100) and a
`recommendation` per attachment. It NEVER reassigns documents — it only
writes rows into `document_assignment_qc_results` for the user to review
and approve.

Severity buckets (used by the UI):
  90..100  ok                — strong evidence supports current assignment
  70..89   minor              — weak evidence, no contradictions
  40..69   suspicious         — some contradicting signals
   0..39   strong_mismatch    — clear contradicting signals
"""
from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

from sqlalchemy.orm import Session

from ..models import (
    EmailAttachment, EmailUpdate, Shipment,
    DocumentAssignmentRule, DocumentAssignmentQcResult,
)

log = logging.getLogger("doc-qc")


# =====================================================================
# Built-in rules — used to seed the table on first run.
# After seeding, edit via the /qc/rules endpoint (admin only).
# =====================================================================

BUILTIN_RULES: List[Dict[str, Any]] = [
    {
        "rule_name": "Polder",
        "supplier_or_brand": "Polder",
        "keywords": [
            "polder", "polder.com", "guangdong kenries", "kenries",
            "ironing board", "ironing boards", "drying rack",
            "פולדר", "קרשי גיהוץ", "קרש גיהוץ", "מתקן לייבוש", "ייבוש כביסה",
        ],
    },
    {
        "rule_name": "Puma / ULAC",
        "supplier_or_brand": "ULAC / Puma United Canada",
        "keywords": [
            "puma", "ulac", "ulac.com", "puma united canada",
            "puma inventory",
        ],
    },
    {
        "rule_name": "Keds",
        "supplier_or_brand": "Keds",
        "keywords": [
            "keds", "e-go footwear", "e- go footwear", "ego footwear",
            "dalian", "נעלי טבע",
        ],
    },
    {
        "rule_name": "Nautica",
        "supplier_or_brand": "Nautica",
        "keywords": [
            "nautica", "נאוטיקה",
            "pillows", "bedding", "כריות", "מצעים",
        ],
    },
    {
        "rule_name": "Lifetime",
        "supplier_or_brand": "Lifetime",
        "keywords": [
            "lifetime", "life time", "lifetime products",
            "coolers", "cooler", "shed", "outdoor",
            "צידניות", "צידנית", "מחסן",
        ],
    },
    {
        "rule_name": "Nandan Terry",
        "supplier_or_brand": "Nandan Terry / A&M Global",
        "keywords": [
            "nandan", "nandan terry", "a&m global", "a & m global",
            "towels", "towel", "bathrobe", "bathrobes",
            "מגבות", "מגבת", "חלוק מגבת",
        ],
    },
]


def seed_builtin_rules(db: Session) -> int:
    """Idempotent — only creates rules that don't exist yet (by rule_name)."""
    existing = {r.rule_name for r in db.query(DocumentAssignmentRule).all()}
    added = 0
    for r in BUILTIN_RULES:
        if r["rule_name"] in existing:
            continue
        db.add(DocumentAssignmentRule(
            rule_name=r["rule_name"],
            supplier_or_brand=r["supplier_or_brand"],
            keywords_json=r["keywords"],
            active=True,
            notes="seeded by system",
        ))
        added += 1
    if added:
        db.commit()
        log.info("Seeded %d document_assignment_rules", added)
    return added


# =====================================================================
# Signal extraction
# =====================================================================

def _gather_signals(att: EmailAttachment, eu: Optional[EmailUpdate]) -> Dict[str, str]:
    """All text we can scan for keyword matches."""
    return {
        "filename":     (att.filename or ""),
        "email_subject": (eu.subject if eu else "") or "",
        "email_sender":  (eu.sender if eu else "") or "",
        "email_body":    ((eu.body_excerpt if eu else "") or "")
                         + " " + ((eu.full_body_text if eu else "") or ""),
        "extracted_text": (att.extracted_text or "") if hasattr(att, "extracted_text") else "",
    }


def _supplier_matches_rule(supplier: Optional[str], rule: DocumentAssignmentRule) -> bool:
    """Does this shipment's supplier name align with this rule?"""
    if not supplier:
        return False
    sup_low = supplier.lower()
    if rule.supplier_or_brand and rule.supplier_or_brand.lower() in sup_low:
        return True
    # Also: any of the rule's keywords found in supplier name
    for kw in (rule.keywords_json or []):
        if kw and kw.lower() in sup_low:
            return True
    return False


def _hits_for_rule(signals: Dict[str, str], rule: DocumentAssignmentRule) -> List[Dict[str, str]]:
    """Find every keyword match for `rule` across all signals."""
    hits: List[Dict[str, str]] = []
    for kw in (rule.keywords_json or []):
        kw_low = (kw or "").lower()
        if not kw_low:
            continue
        for sig_name, sig_text in signals.items():
            if not sig_text:
                continue
            if kw_low in sig_text.lower():
                hits.append({
                    "rule": rule.rule_name,
                    "supplier": rule.supplier_or_brand,
                    "keyword": kw,
                    "signal": sig_name,
                })
    return hits


# =====================================================================
# Scoring
# =====================================================================

# Per-signal weights (signals more authoritative than filename get higher)
SIGNAL_WEIGHTS = {
    "email_subject": 30,
    "email_sender":  35,   # sender domain is the strongest signal
    "email_body":    20,
    "filename":      15,
    "extracted_text": 18,
}


def _score_for_rule(hits: List[Dict[str, str]]) -> int:
    """Sum the per-signal weights for this rule's hits, capped at 100."""
    by_signal: Dict[str, int] = {}
    for h in hits:
        sig = h["signal"]
        # one hit per (signal) is enough — don't double-count many keywords
        # in the same signal
        by_signal[sig] = max(by_signal.get(sig, 0), SIGNAL_WEIGHTS.get(sig, 10))
    return min(100, sum(by_signal.values()))


def _severity(score: int) -> str:
    if score >= 90: return "ok"
    if score >= 70: return "minor"
    if score >= 40: return "suspicious"
    return "strong_mismatch"


# =====================================================================
# Per-attachment audit
# =====================================================================

def audit_attachment(
    db: Session,
    att: EmailAttachment,
    rules: List[DocumentAssignmentRule],
    shipments: List[Shipment],
) -> Dict[str, Any]:
    """Returns a dict with the QC result for ONE attachment.

    The dict mirrors the `document_assignment_qc_results` columns.
    Caller persists it (or compares to the existing latest open result).
    """
    eu = None
    if att.email_update_id:
        eu = db.query(EmailUpdate).filter(EmailUpdate.id == att.email_update_id).first()
    signals = _gather_signals(att, eu)

    # Per-rule hits
    rule_to_hits: Dict[int, List[Dict[str, str]]] = {}
    rule_to_score: Dict[int, int] = {}
    for rule in rules:
        if not rule.active:
            continue
        hits = _hits_for_rule(signals, rule)
        if hits:
            rule_to_hits[rule.id] = hits
            rule_to_score[rule.id] = _score_for_rule(hits)

    # Score for the *currently linked* shipment: how well do its rules match?
    current = next((s for s in shipments if s.id == att.linked_shipment_id), None) \
              if att.linked_shipment_id else None

    matching_rules_for_current = [r for r in rules if r.active
                                  and _supplier_matches_rule(current.supplier if current else None, r)]
    current_score = max((rule_to_score.get(r.id, 0) for r in matching_rules_for_current),
                        default=0)

    # Best alternative: any shipment whose supplier matches rules with hits
    alt_best_shipment_id: Optional[int] = None
    alt_best_score = 0
    alt_best_rule_id: Optional[int] = None
    for rule_id, score in rule_to_score.items():
        if score < 30:  # too weak to suggest
            continue
        rule = next((r for r in rules if r.id == rule_id), None)
        if not rule:
            continue
        for s in shipments:
            if not _supplier_matches_rule(s.supplier, rule):
                continue
            if s.id == att.linked_shipment_id:
                continue
            # An alternative shipment that this rule points at
            if score > alt_best_score:
                alt_best_score = score
                alt_best_shipment_id = s.id
                alt_best_rule_id = rule_id

    # Determine severity + recommendation
    mismatch_reasons: List[str] = []
    matched_signals: List[Dict[str, str]] = []
    for hits in rule_to_hits.values():
        matched_signals.extend(hits)

    if not att.linked_shipment_id:
        # Unassigned — the QC isn't about a wrong link, but about a probable home
        if alt_best_shipment_id:
            confidence = 30  # low because we don't have any "current" baseline
            recommendation = "reassign_suggested"
            severity = "suspicious"
            sup = next((s.supplier for s in shipments if s.id == alt_best_shipment_id), "?")
            mismatch_reasons.append(
                f"מסמך לא משויך — סימני {sup} זוהו (score {alt_best_score})"
            )
        else:
            confidence = 50
            recommendation = "review"
            severity = "suspicious"
            mismatch_reasons.append("מסמך לא משויך, ולא נמצאה התאמה ברורה")
    elif alt_best_shipment_id and alt_best_score >= max(60, current_score + 30):
        # An alternative shipment matches markedly better than the current one
        confidence = max(0, current_score - alt_best_score)  # negative-ish → low
        if confidence < 0:
            confidence = 0
        recommendation = "reassign_suggested"
        severity = _severity(confidence)
        alt_sup = next((s.supplier for s in shipments
                        if s.id == alt_best_shipment_id), "?")
        cur_sup = current.supplier if current else "?"
        mismatch_reasons.append(
            f"המשלוח הנוכחי הוא {cur_sup} אבל הסימנים מצביעים על {alt_sup} "
            f"(score {alt_best_score} מול {current_score})"
        )
        # Also enumerate the specific keyword hits that drove the suggestion
        rule = next((r for r in rules if r.id == alt_best_rule_id), None)
        if rule:
            for h in rule_to_hits.get(alt_best_rule_id, [])[:5]:
                mismatch_reasons.append(
                    f"מילת מפתח '{h['keyword']}' נמצאה ב-{h['signal']}"
                )
    elif current_score >= 70:
        confidence = current_score
        recommendation = "keep"
        severity = _severity(confidence)
    elif current_score > 0:
        confidence = current_score
        recommendation = "review"
        severity = _severity(confidence)
        mismatch_reasons.append(
            f"התאמה חלקית בלבד למשלוח הנוכחי (score {current_score})"
        )
    else:
        # No signals match either current or any alternative
        confidence = 50
        recommendation = "review"
        severity = "suspicious"
        mismatch_reasons.append(
            "לא נמצאו סימני ספק/מותג מובהקים — דרושה בדיקה ידנית"
        )

    return {
        "document_id": att.id,
        "current_shipment_id": att.linked_shipment_id,
        "suspected_shipment_id": alt_best_shipment_id,
        "confidence_score": int(confidence),
        "severity": severity,
        "recommendation": recommendation,
        "mismatch_reasons_json": mismatch_reasons,
        "matched_signals_json": matched_signals[:20],
    }


# =====================================================================
# Full scan
# =====================================================================

def run_scan(db: Session, *, only_doc_ids: Optional[List[int]] = None) -> Dict[str, Any]:
    """Scan every linked + unassigned attachment, write/update QC results.

    NEVER mutates `email_attachments.linked_shipment_id`.
    """
    rules = db.query(DocumentAssignmentRule).filter(
        DocumentAssignmentRule.active == True   # noqa: E712
    ).all()
    if not rules:
        seed_builtin_rules(db)
        rules = db.query(DocumentAssignmentRule).filter(
            DocumentAssignmentRule.active == True  # noqa: E712
        ).all()

    shipments = db.query(Shipment).filter(Shipment.archived == False).all()  # noqa: E712

    q = db.query(EmailAttachment).filter(
        EmailAttachment.archived == False  # noqa: E712 — never QC-flag archived rows
    )
    if only_doc_ids:
        q = q.filter(EmailAttachment.id.in_(only_doc_ids))
    attachments = q.all()

    counts = {"scanned": 0, "ok": 0, "minor": 0,
              "suspicious": 0, "strong_mismatch": 0}
    new_alerts = 0
    superseded = 0

    for att in attachments:
        verdict = audit_attachment(db, att, rules, shipments)
        counts["scanned"] += 1
        sev = verdict["severity"]
        counts[sev] = counts.get(sev, 0) + 1

        # Look up the latest OPEN result for this document
        latest_open = (
            db.query(DocumentAssignmentQcResult)
            .filter(DocumentAssignmentQcResult.document_id == att.id,
                    DocumentAssignmentQcResult.status == "open")
            .order_by(DocumentAssignmentQcResult.id.desc())
            .first()
        )

        # If a previous result exists and the verdict hasn't changed
        # meaningfully, skip — don't churn history.
        if latest_open and (
            latest_open.severity == sev
            and latest_open.suspected_shipment_id == verdict["suspected_shipment_id"]
            and latest_open.confidence_score == verdict["confidence_score"]
        ):
            continue

        # Supersede any previous open result so the UI shows the freshest one
        if latest_open:
            latest_open.status = "superseded"
            latest_open.resolved_at = datetime.utcnow()
            latest_open.resolution_action = "superseded_by_rescan"
            superseded += 1

        # Only persist if there's something interesting (non-ok) to surface
        if sev == "ok":
            continue

        new = DocumentAssignmentQcResult(
            document_id=verdict["document_id"],
            current_shipment_id=verdict["current_shipment_id"],
            suspected_shipment_id=verdict["suspected_shipment_id"],
            confidence_score=verdict["confidence_score"],
            severity=verdict["severity"],
            status="open",
            mismatch_reasons_json=verdict["mismatch_reasons_json"],
            matched_signals_json=verdict["matched_signals_json"],
            recommendation=verdict["recommendation"],
        )
        db.add(new)
        new_alerts += 1

    db.commit()

    summary = {
        **counts,
        "open_alerts_created": new_alerts,
        "superseded_results": superseded,
    }
    log.info("QC scan complete: %s", summary)
    return summary
