"""
upsell_engine.py — Real-Time Upsell Suggestions
==================================================
Suggests high-margin items that pair well with
the customer's current order. Uses sales co-occurrence
data from the database.
"""

import logging
from collections import Counter

from sqlalchemy.orm import Session
from sqlalchemy import func

from models import MenuItem, SaleTransaction

logger = logging.getLogger("petpooja.voice.upsell")


def suggest_upsells(
    db: Session,
    ordered_item_ids: list[int],
    max_suggestions: int = 3,
    min_margin_pct: float = 55.0,
) -> list[dict]:
    """
    Suggest upsell items based on what's already in the order.

    Strategy:
    1. Find items frequently co-ordered with current items
    2. Filter for high-margin items (we want profitable upsells)
    3. Exclude items already in the order
    4. Rank by (co-occurrence × margin)

    Args:
        db: Database session
        ordered_item_ids: IDs of items already in the order
        max_suggestions: Max number of upsell suggestions
        min_margin_pct: Minimum margin % for upsell candidates

    Returns:
        List of upsell suggestion dicts
    """
    if not ordered_item_ids:
        return []

    # Find orders that contain the current items
    related_order_ids = (
        db.query(SaleTransaction.order_id)
        .filter(SaleTransaction.item_id.in_(ordered_item_ids))
        .distinct()
        .limit(500)
        .all()
    )
    related_orders = [r[0] for r in related_order_ids]

    if not related_orders:
        return _fallback_suggestions(db, ordered_item_ids, max_suggestions)

    # Find items frequently in those same orders
    co_items = (
        db.query(
            SaleTransaction.item_id,
            func.count(SaleTransaction.id).label("co_count"),
        )
        .filter(
            SaleTransaction.order_id.in_(related_orders),
            ~SaleTransaction.item_id.in_(ordered_item_ids),
        )
        .group_by(SaleTransaction.item_id)
        .order_by(func.count(SaleTransaction.id).desc())
        .limit(20)
        .all()
    )

    if not co_items:
        return _fallback_suggestions(db, ordered_item_ids, max_suggestions)

    # Get item details and filter by margin
    suggestions = []
    for item_id, co_count in co_items:
        item = db.query(MenuItem).get(item_id)
        if not item or not item.is_available:
            continue

        margin_pct = item.margin_pct
        if margin_pct < min_margin_pct:
            continue

        # Score = co-occurrence × margin %
        score = co_count * (margin_pct / 100)

        suggestion_text = _generate_suggestion_text(item)

        suggestions.append({
            "item_id": item.id,
            "name": item.name,
            "name_hi": item.name_hi or "",
            "selling_price": item.selling_price,
            "margin_pct": round(margin_pct, 1),
            "co_order_count": co_count,
            "upsell_score": round(score, 2),
            "suggestion_text": suggestion_text,
            "is_veg": item.is_veg,
        })

        if len(suggestions) >= max_suggestions:
            break

    suggestions.sort(key=lambda x: x["upsell_score"], reverse=True)
    return suggestions


def _fallback_suggestions(
    db: Session, exclude_ids: list[int], limit: int
) -> list[dict]:
    """Fallback: suggest top-margin items not in the order."""
    items = (
        db.query(MenuItem)
        .filter(
            MenuItem.is_available == True,
            ~MenuItem.id.in_(exclude_ids),
        )
        .all()
    )

    scored = []
    for item in items:
        if item.margin_pct >= 60:
            scored.append({
                "item_id": item.id,
                "name": item.name,
                "name_hi": item.name_hi or "",
                "selling_price": item.selling_price,
                "margin_pct": round(item.margin_pct, 1),
                "co_order_count": 0,
                "upsell_score": round(item.margin_pct, 2),
                "suggestion_text": _generate_suggestion_text(item),
                "is_veg": item.is_veg,
            })

    scored.sort(key=lambda x: x["upsell_score"], reverse=True)
    return scored[:limit]


def _generate_suggestion_text(item: MenuItem) -> str:
    """Generate a natural upsell suggestion."""
    if item.is_bestseller:
        return f"Our bestseller {item.name} goes great with your order! ₹{item.selling_price}"
    elif "chef-special" in (item.tags or []):
        return f"Try our chef's special {item.name}? Just ₹{item.selling_price}"
    else:
        return f"Would you like to add {item.name}? Only ₹{item.selling_price}"
