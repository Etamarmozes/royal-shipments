"""Product category — controlled list + heuristic detection from email text.

The category list is fixed (UI shows a dropdown). Detection uses keyword
mapping over Hebrew + English. Detection NEVER overwrites a manually-set
category — that's enforced by the caller (email_apply_service).
"""
from __future__ import annotations

import re
from typing import Optional, List

# Controlled list — UI displays these in this exact order.
CATEGORIES: List[str] = [
    "הלבשה תחתונה",
    "ביגוד",
    "מצעים",
    "שמיכות וכריות",
    "מגבות",
    "מוצרי חשמל",
    "צעצועים",
    "כלי בית",
    "אחסון / מחסן",
    "נעליים",
    "אחר",
]

DEFAULT_CATEGORY = "אחר"


# Keyword → category mapping. Order matters slightly (more specific first).
# Each entry: (regex, category). Case-insensitive.
_KEYWORD_RULES: List[tuple[str, str]] = [
    # bedding / sheets
    (r"\b(bedding|bed\s+linen|sheets?|fitted\s+sheet|flat\s+sheet)\b|מצעים|סדינים", "מצעים"),
    # blankets / pillows / duvet
    (r"\b(blankets?|pillows?|duvets?|comforters?|cushions?)\b|שמיכות|כריות|שמיכה|כרית", "שמיכות וכריות"),
    # towels  (ironing boards are NOT towels — handled separately below)
    (r"\b(towels?|bath\s+towel|hand\s+towel|terry)\b|מגבות|מגבת", "מגבות"),
    # underwear / socks
    (r"\b(underwear|socks?|panties|bras?|briefs?|boxers?)\b|הלבשה\s+תחתונה|גרביים", "הלבשה תחתונה"),
    # clothing / apparel
    (r"\b(clothing|apparel|shirts?|pants?|jeans?|t[\-\s]?shirts?|hoodies?|jackets?)\b|ביגוד|חולצות|מכנסיים", "ביגוד"),
    # electronics
    (r"\b(electronics|appliances|electric|electronic)\b|מוצרי\s+חשמל|חשמל", "מוצרי חשמל"),
    # toys
    (r"\b(toys?|lego|puzzles?|board\s+games?)\b|צעצועים|משחקים", "צעצועים"),
    # storage
    (r"\b(storage|shed|warehouse(?:\s+goods)?)\b|אחסון|מחסן", "אחסון / מחסן"),
    # shoes
    (r"\b(shoes?|footwear|sneakers?|boots?|sandals?)\b|נעליים", "נעליים"),
    # kitchen / houseware
    (r"\b(kitchen|houseware|home\s+goods|cookware|tableware|ironing\s+boards?)\b|כלי\s+בית", "כלי בית"),
]

_COMPILED = [(re.compile(rx, re.IGNORECASE), cat) for rx, cat in _KEYWORD_RULES]


def detect_category(*texts: Optional[str]) -> Optional[str]:
    """Run keyword detection across all provided text fragments.
    Returns the first matching category, or None if no match.
    Caller decides what to do with None (typically: leave as-is or set 'אחר')."""
    blob = " ".join(t for t in texts if t)
    if not blob.strip():
        return None
    for rx, cat in _COMPILED:
        if rx.search(blob):
            return cat
    return None


def is_valid_category(c: Optional[str]) -> bool:
    return bool(c and c in CATEGORIES)


def normalize_category(c: Optional[str]) -> str:
    """Coerce a free-text category value into the controlled list. Unknown → 'אחר'."""
    if not c:
        return DEFAULT_CATEGORY
    c = c.strip()
    if c in CATEGORIES:
        return c
    return DEFAULT_CATEGORY


def effective_container_category(container, shipment) -> Optional[str]:
    """Return container.category if set, else fall back to shipment.category."""
    if container and container.category:
        return container.category
    if shipment and shipment.category:
        return shipment.category
    return None
