"""
Anthropic tool-use agent.

When ANTHROPIC_API_KEY is set, the user's question is answered by Claude
calling the analytics tools. Otherwise a deterministic fallback handles
the most common questions using the same tools.
"""
from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy.orm import Session

from ..config import settings
from ..models import AIAnalysisLog
from ..utils.logging import get_logger
from .tools import TOOL_DEFINITIONS, call_tool

log = get_logger(__name__)

SYSTEM_PROMPT = """You are the Sales Intelligence assistant for a retail chain.

Your audience is the CEO and commercial managers. Be concise, decision-grade.

Rules:
- Use the provided tools to fetch real numbers. Never invent figures.
- If a tool returns no data, say so plainly. Do not guess.
- Answer in the language of the question (Hebrew for Hebrew, English for English).
- Every answer follows this structure:
  1. Bottom line (one sentence)
  2. Key numbers (3-5 figures with units)
  3. What it means (interpretation)
  4. Problem / opportunity
  5. Recommended action (start with a verb)
  6. Data limitations / confidence
- Use plain text. No markdown headings.
"""


def _fallback_answer(db: Session, question: str) -> dict:
    """Deterministic, rule-based answer when no API key is configured."""
    q = question.lower()

    def used(t, args, result):
        return [{"tool": t, "args": args, "result_preview": json.dumps(result, default=str)[:400]}]

    # brand comparison?
    m = re.search(r"(keds|adidas|nautica|lifetime).{0,40}(keds|adidas|nautica|lifetime)", q)
    if m or "מול" in q:
        brand_a, brand_b = "Keds", "Adidas"
        if m:
            brand_a, brand_b = m.group(1).capitalize(), m.group(2).capitalize()
        result = call_tool(db, "compare_brands",
                           {"brand_a": brand_a, "brand_b": brand_b, "date_range": "this_month"})
        a_total = result.get("a", {}).get("net_sales", 0)
        b_total = result.get("b", {}).get("net_sales", 0)
        leader = brand_a if a_total > b_total else brand_b
        text = (
            f"Bottom line: {leader} leads chain-wide this month.\n"
            f"Key numbers: {brand_a} {a_total:,.0f} ₪ vs {brand_b} {b_total:,.0f} ₪.\n"
            f"What it means: {result.get('insight', '')}\n"
            f"Problem/opportunity: track per-store distribution to align assortment with store type.\n"
            f"Recommended action: keep {brand_a} weighted to value/outlet stores and {brand_b} to flagship/general.\n"
            f"Data limitations: based only on imported sales. Inventory not factored here."
        )
        return {"answer": text, "tool_calls": used("compare_brands",
                {"brand_a": brand_a, "brand_b": brand_b, "date_range": "this_month"}, result)}

    if any(w in q for w in ["ceo", "מנכ", "סיכום", "summary"]):
        result = call_tool(db, "generate_ceo_summary", {"date_range": "this_month"})
        text = (
            f"Bottom line: {result.get('period_label')} — net sales "
            f"{result['headline_metrics']['net_sales']:,.0f} ₪ "
            f"({result['headline_metrics']['vs_prev_pct']}% vs previous).\n"
            f"Key numbers: units {result['headline_metrics']['units']:,.0f}.\n"
            f"What it means: " + " | ".join(result.get("wins", [])) + "\n"
            f"Problem: " + " | ".join(result.get("problems", [])) + "\n"
            f"Recommended actions: " + "; ".join(a["action"] + " — " + a["target"]
                                                  for a in result.get("actions", [])) + "\n"
            f"Watch: {result.get('watch_this_week')}"
        )
        return {"answer": text, "tool_calls": used("generate_ceo_summary",
                {"date_range": "this_month"}, result)}

    if any(w in q for w in ["risk", "מלאי", "תקועים", "reorder", "הזמ", "stuck"]):
        result = call_tool(db, "detect_inventory_risks", {"days_lookback": 30})
        f = len(result.get("fast_moving_low_stock", []))
        s = len(result.get("slow_moving_high_stock", []))
        st = len(result.get("stuck_items", []))
        text = (
            f"Bottom line: inventory risk scan — {f} stockout risks, {s} slow movers, {st} stuck items.\n"
            f"Key numbers: see full list in /api/dashboard or report generator.\n"
            f"What it means: stockout risks affect revenue today; stuck items tie up capital.\n"
            f"Problem: prioritize the stockout-in-strong-stores list (highest sales loss).\n"
            f"Recommended action: reorder the top 5 fast-moving items and transfer from slow-moving stores where possible.\n"
            f"Data limitations: based on the latest inventory snapshot per store."
        )
        return {"answer": text, "tool_calls": used("detect_inventory_risks",
                {"days_lookback": 30}, result)}

    # default: top items + summary
    summary = call_tool(db, "get_sales_summary", {"date_range": "this_month"})
    top = call_tool(db, "get_top_items", {"date_range": "this_month", "limit": 5})
    top_line = ", ".join(f"{r['item_name']} ({r['value']:,.0f}₪)" for r in top[:3])
    text = (
        f"Bottom line: {summary['period_label']} net sales {summary['net_sales']:,.0f} ₪.\n"
        f"Key numbers: units {summary['units']:,.0f} · AOV {summary['avg_selling_price']:.0f} ₪ "
        f"· vs prev {summary['vs_previous_period']['delta_pct']}%.\n"
        f"What it means: top contributors — {top_line}.\n"
        f"Problem/opportunity: review the bottom-of-list items for promo or delisting.\n"
        f"Recommended action: hold a 15-minute commercial sync to confirm reorder priorities.\n"
        f"Data limitations: numbers reflect imported reports only."
    )
    return {"answer": text,
            "tool_calls": used("get_sales_summary + get_top_items", {"date_range": "this_month"},
                               {"summary": summary, "top": top})}


def _claude_answer(db: Session, question: str) -> dict:
    from anthropic import Anthropic

    client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    messages: list[dict[str, Any]] = [{"role": "user", "content": question}]
    tool_log: list[dict] = []

    for _ in range(8):  # safety: max 8 round trips
        resp = client.messages.create(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=TOOL_DEFINITIONS,
            messages=messages,
        )
        # collect any tool_use blocks
        tool_uses = [b for b in resp.content if getattr(b, "type", "") == "tool_use"]
        if not tool_uses:
            text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
            return {"answer": text.strip(), "tool_calls": tool_log}

        # execute and feed back
        messages.append({"role": "assistant", "content": resp.content})
        tool_results = []
        for tu in tool_uses:
            result = call_tool(db, tu.name, tu.input or {})
            tool_log.append({
                "tool": tu.name,
                "args": tu.input,
                "result_preview": json.dumps(result, default=str)[:500],
            })
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tu.id,
                "content": json.dumps(result, default=str),
            })
        messages.append({"role": "user", "content": tool_results})

    return {"answer": "I ran out of analysis steps. Please narrow the question.",
            "tool_calls": tool_log}


def answer_question(db: Session, question: str) -> dict:
    if settings.ANTHROPIC_API_KEY:
        try:
            result = _claude_answer(db, question)
            mode = "claude"
        except Exception as e:
            log.exception("ai.claude_error")
            result = _fallback_answer(db, question)
            result["answer"] = result["answer"] + f"\n\n(AI fallback used: {e.__class__.__name__})"
            mode = "fallback_after_error"
    else:
        result = _fallback_answer(db, question)
        mode = "fallback_no_key"

    # log
    try:
        log_row = AIAnalysisLog(
            question=question,
            answer=result["answer"],
            tools_used=json.dumps(result.get("tool_calls", []), ensure_ascii=False, default=str),
            data_sources_used=json.dumps({"mode": mode}),
        )
        db.add(log_row)
        db.commit()
    except Exception:
        log.exception("ai.log_error")
        db.rollback()

    result["mode"] = mode
    return result
