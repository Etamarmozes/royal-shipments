"""
Generate executive reports as PNG / JPG / PDF.

Strategy: build the report as a single matplotlib figure (Hebrew-safe via
text-direction reversing), save to bytes, then save to disk in the chosen format.
This is dependency-light: no wkhtmltoimage, no playwright, no system fonts.

For higher-fidelity HTML/CSS reports later, swap the renderer with playwright
or imgkit — the analytics result stays the same.
"""
from __future__ import annotations

import json
import unicodedata
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

from sqlalchemy.orm import Session  # noqa: E402

from ..analytics import (  # noqa: E402
    compare_brands,
    generate_action_plan,
    generate_ceo_summary,
    get_sales_summary,
    get_store_ranking,
)
from ..config import settings  # noqa: E402
from ..models import GeneratedReport  # noqa: E402

LAYOUTS = {
    "whatsapp": (1080, 1920),
    "desktop": (1600, 900),
    "ceo_one_pager": (2480, 3508),
    "store_ranking": (1600, 1200),
    "brand_comparison": (1600, 1200),
}


def _is_hebrew(s: str) -> bool:
    return any("֐" <= ch <= "׿" for ch in (s or ""))


def _bidi(s: str) -> str:
    """Cheap Hebrew bidi fix for matplotlib (which doesn't have a bidi engine).
    Reverses Hebrew runs so they render visually L-to-R correctly."""
    if not _is_hebrew(s):
        return s
    return s[::-1]


def _kpi_box(ax, x, y, w, h, label: str, value: str, sub: str = "", color="#1e3a8a"):
    box = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.02",
                         linewidth=0, facecolor=color, alpha=0.08)
    ax.add_patch(box)
    ax.text(x + 0.02, y + h - 0.05, _bidi(label), fontsize=11, color=color, alpha=0.9)
    ax.text(x + 0.02, y + h * 0.45, value, fontsize=22, color=color, weight="bold")
    if sub:
        ax.text(x + 0.02, y + 0.04, _bidi(sub), fontsize=10, color="#475569")


def _save(fig, fmt: str, out_dir: Path, base_name: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    safe = unicodedata.normalize("NFKC", base_name).replace(" ", "_")
    if fmt in {"jpg", "jpeg"}:
        path = out_dir / f"{safe}_{ts}.jpg"
        fig.savefig(path, format="jpeg", dpi=150, bbox_inches="tight", facecolor="white")
    elif fmt == "pdf":
        path = out_dir / f"{safe}_{ts}.pdf"
        fig.savefig(path, format="pdf", bbox_inches="tight", facecolor="white")
    else:
        path = out_dir / f"{safe}_{ts}.png"
        fig.savefig(path, format="png", dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def _figure(layout: str):
    w_px, h_px = LAYOUTS.get(layout, (1600, 900))
    dpi = 150
    fig = plt.figure(figsize=(w_px / dpi, h_px / dpi), dpi=dpi)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    return fig, ax


def _header(ax, title: str, subtitle: str):
    ax.text(0.04, 0.94, _bidi(title), fontsize=22, weight="bold", color="#0f172a")
    ax.text(0.04, 0.905, _bidi(subtitle), fontsize=12, color="#475569")
    ax.plot([0.04, 0.96], [0.89, 0.89], color="#cbd5e1", linewidth=1)


def _footer(ax, sources: list[str]):
    ax.text(0.04, 0.02, f"Generated {datetime.now():%Y-%m-%d %H:%M} · " + " · ".join(sources),
            fontsize=9, color="#64748b")


def _render_ceo_summary(payload: dict, layout: str) -> "plt.Figure":
    fig, ax = _figure(layout)
    _header(
        ax,
        f"CEO summary — {payload.get('period_label', '')}",
        f"Net sales {payload['headline_metrics']['net_sales']:,.0f} ₪ · "
        f"Units {payload['headline_metrics']['units']:,.0f} · "
        f"vs prev {payload['headline_metrics'].get('vs_prev_pct', 0)}%",
    )

    _kpi_box(ax, 0.04, 0.78, 0.27, 0.08, "Net sales",
             f"{payload['headline_metrics']['net_sales']:,.0f} ₪",
             color="#1e3a8a")
    _kpi_box(ax, 0.36, 0.78, 0.27, 0.08, "Units",
             f"{payload['headline_metrics']['units']:,.0f}",
             color="#0e7490")
    _kpi_box(ax, 0.68, 0.78, 0.28, 0.08, "vs previous",
             f"{payload['headline_metrics'].get('vs_prev_pct', 0)}%",
             color="#15803d")

    y = 0.7
    ax.text(0.04, y, "Wins", fontsize=14, weight="bold", color="#15803d")
    for w in payload.get("wins", [])[:3]:
        y -= 0.045
        ax.text(0.06, y, "✓ " + w, fontsize=12, color="#0f172a")

    y -= 0.06
    ax.text(0.04, y, "Problems", fontsize=14, weight="bold", color="#b91c1c")
    for p in payload.get("problems", [])[:3]:
        y -= 0.045
        ax.text(0.06, y, "▲ " + p, fontsize=12, color="#0f172a")

    y -= 0.06
    ax.text(0.04, y, "Recommended actions", fontsize=14, weight="bold", color="#1e3a8a")
    for a in payload.get("actions", [])[:3]:
        y -= 0.05
        ax.text(0.06, y, f"▶ [{a['priority']}] {a['action']} — {a['target']}",
                fontsize=11, color="#0f172a")
        y -= 0.025
        ax.text(0.08, y, a.get("why", ""), fontsize=9, color="#475569")

    if payload.get("watch_this_week"):
        ax.text(0.04, 0.10, "Watch this week: " + payload["watch_this_week"],
                fontsize=11, color="#7c3aed", style="italic")

    _footer(ax, ["sales", "inventory"])
    return fig


def _render_brand_comparison(payload: dict, layout: str) -> "plt.Figure":
    fig, ax = _figure(layout)
    title = f"{payload['brand_a']} vs {payload['brand_b']}"
    _header(ax, title, payload.get("period_label", ""))

    a_total = payload["a"]["net_sales"]
    b_total = payload["b"]["net_sales"]
    _kpi_box(ax, 0.04, 0.78, 0.45, 0.10,
             f"{payload['brand_a']} net sales",
             f"{a_total:,.0f} ₪",
             sub=f"Units {payload['a']['units']:,.0f}", color="#1e3a8a")
    _kpi_box(ax, 0.51, 0.78, 0.45, 0.10,
             f"{payload['brand_b']} net sales",
             f"{b_total:,.0f} ₪",
             sub=f"Units {payload['b']['units']:,.0f}", color="#b91c1c")

    # head-to-head bar chart inset
    h2h = payload.get("head_to_head", [])[:8]
    if h2h:
        ax2 = fig.add_axes([0.06, 0.18, 0.6, 0.5])
        names = [r["store_name"] for r in h2h]
        a_vals = [r["a"] for r in h2h]
        b_vals = [r["b"] for r in h2h]
        y_pos = range(len(names))
        ax2.barh([y - 0.2 for y in y_pos], a_vals, height=0.4,
                 color="#1e3a8a", label=payload["brand_a"])
        ax2.barh([y + 0.2 for y in y_pos], b_vals, height=0.4,
                 color="#b91c1c", label=payload["brand_b"])
        ax2.set_yticks(list(y_pos))
        ax2.set_yticklabels(names, fontsize=9)
        ax2.invert_yaxis()
        ax2.legend(loc="lower right", fontsize=9)
        ax2.set_xlabel("Net sales (₪)")
        ax2.spines["top"].set_visible(False)
        ax2.spines["right"].set_visible(False)

    insight = payload.get("insight", "")
    ax.text(0.68, 0.66, "Insight", fontsize=12, weight="bold", color="#0f172a")
    ax.text(0.68, 0.45, _bidi(insight), fontsize=10, color="#0f172a", wrap=True)

    ax.text(0.68, 0.32, "Recommendation", fontsize=12, weight="bold", color="#0f172a")
    rec = (
        f"Keep {payload['brand_a']} weighted to value/outlet stores; "
        f"keep {payload['brand_b']} as the premium anchor in flagship/general stores."
    )
    ax.text(0.68, 0.18, rec, fontsize=10, color="#0f172a", wrap=True)

    _footer(ax, ["sales"])
    return fig


def _render_store_ranking(payload: list[dict], layout: str, period_label: str) -> "plt.Figure":
    fig, ax = _figure(layout)
    _header(ax, "Store ranking", period_label)

    rows = payload[:10]
    if rows:
        ax2 = fig.add_axes([0.06, 0.12, 0.9, 0.7])
        names = [r["store_name"] for r in rows]
        vals = [r["value"] for r in rows]
        ax2.barh(range(len(names)), vals, color="#1e3a8a")
        ax2.set_yticks(range(len(names)))
        ax2.set_yticklabels(names, fontsize=11)
        ax2.invert_yaxis()
        ax2.set_xlabel("Net sales (₪)")
        ax2.spines["top"].set_visible(False)
        ax2.spines["right"].set_visible(False)
        for i, r in enumerate(rows):
            delta = r.get("vs_prev_pct")
            label = f"  {r['value']:,.0f} ₪"
            if delta is not None:
                color = "#15803d" if delta >= 0 else "#b91c1c"
                ax2.text(r["value"], i, label + f"  ({delta:+.1f}%)",
                         va="center", fontsize=10, color=color)
            else:
                ax2.text(r["value"], i, label, va="center", fontsize=10)

    _footer(ax, ["sales"])
    return fig


def generate_report(
    db: Session,
    topic: str,
    date_range: Any = "this_month",
    fmt: str = "png",
    layout: str = "desktop",
    params: dict | None = None,
) -> dict:
    params = params or {}
    fmt = (fmt or "png").lower()

    if topic == "ceo_summary":
        payload = generate_ceo_summary(db, date_range)
        fig = _render_ceo_summary(payload, layout)
        title = f"CEO summary — {payload.get('period_label')}"
        base = "ceo_summary"
    elif topic == "brand_comparison":
        a = params.get("brand_a", "Keds")
        b = params.get("brand_b", "Adidas")
        payload = compare_brands(db, a, b, date_range)
        fig = _render_brand_comparison(payload, layout)
        title = f"{a} vs {b} — {payload.get('period_label')}"
        base = f"brand_{a.lower()}_vs_{b.lower()}"
    elif topic == "store_ranking":
        ranking = get_store_ranking(db, date_range)
        period_label = get_sales_summary(db, date_range)["period_label"]
        fig = _render_store_ranking(ranking, layout, period_label)
        title = f"Store ranking — {period_label}"
        base = "store_ranking"
        payload = ranking
    elif topic == "action_plan":
        payload = generate_action_plan(db, date_range)
        # render as a CEO-summary style page
        fake = {
            "period_label": str(date_range),
            "headline_metrics": {"net_sales": 0, "units": 0, "vs_prev_pct": 0},
            "wins": [], "problems": [], "actions": payload.get("actions", []),
            "watch_this_week": "",
        }
        fig = _render_ceo_summary(fake, layout)
        title = "Action plan"
        base = "action_plan"
    else:
        raise ValueError(f"Unknown report topic: {topic}")

    out_dir = settings.REPORTS_DIR / fmt
    path = _save(fig, fmt, out_dir, base)

    row = GeneratedReport(
        report_type=topic,
        title=title,
        file_path=str(path),
        format=fmt,
        parameters_json=json.dumps({"layout": layout, "date_range": str(date_range), **params},
                                    ensure_ascii=False),
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    return {
        "id": row.id,
        "title": title,
        "file_path": str(path),
        "format": fmt,
        "topic": topic,
    }
