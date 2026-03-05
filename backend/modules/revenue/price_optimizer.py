"""
price_optimizer.py — Rule-Based Price Recommendations
======================================================
No external APIs — uses pure rule-based logic to suggest
price adjustments based on margin gaps, velocity, and
category benchmarks.
"""


def generate_price_recommendations(
    margins: list[dict],
    popularity: list[dict],
    target_margin_pct: float = 65.0,
    max_increase_pct: float = 12.0,
    max_decrease_pct: float = 8.0,
) -> list[dict]:
    """
    Generate price recommendations based on margin and popularity.

    Rules:
    1. Low margin + High popularity → Increase price (customers already love it)
    2. High margin + Low popularity → Small decrease or hold (price may be barrier)
    3. Low margin + Low popularity → Consider removing or reworking
    4. High margin + High popularity → Hold (it's working perfectly)

    Returns:
        List of price recommendation dicts
    """
    pop_map = {p["item_id"]: p for p in popularity}
    recommendations = []

    for m in margins:
        item_id = m["item_id"]
        pop = pop_map.get(item_id, {})
        pop_score = pop.get("popularity_score", 0)
        margin_pct = m["margin_pct"]
        current_price = m["selling_price"]
        food_cost = m["food_cost"]

        high_margin = margin_pct >= target_margin_pct
        high_pop = pop_score >= 0.4

        if not high_margin and high_pop:
            # Plowhorse: popular but low margin — carefully raise price
            gap = target_margin_pct - margin_pct
            increase_pct = min(gap * 0.4, max_increase_pct)
            new_price = _round_price(current_price * (1 + increase_pct / 100))

            rec = _build_rec(
                m, pop, "increase", increase_pct, new_price,
                f"Popular item with low margin ({margin_pct:.1f}%). "
                f"Customers already love it — a small price increase won't hurt demand.",
                confidence=0.8,
                priority="high",
            )

        elif not high_margin and not high_pop:
            # Dog: low margin + low pop — needs serious attention
            if margin_pct < 40:
                rec = _build_rec(
                    m, pop, "review", 0, current_price,
                    f"Low margin ({margin_pct:.1f}%) and low demand. "
                    f"Consider removing from menu or reworking the recipe to cut costs.",
                    confidence=0.7,
                    priority="critical",
                )
            else:
                increase_pct = min(target_margin_pct - margin_pct, max_increase_pct)
                new_price = _round_price(current_price * (1 + increase_pct / 100))
                rec = _build_rec(
                    m, pop, "increase", increase_pct, new_price,
                    f"Underperforming item. Raise price to improve margin, "
                    f"or bundle with popular items.",
                    confidence=0.6,
                    priority="medium",
                )

        elif high_margin and not high_pop:
            # Puzzle: profitable but not selling
            if margin_pct > 75:
                decrease_pct = min((margin_pct - 70) * 0.3, max_decrease_pct)
                new_price = _round_price(current_price * (1 - decrease_pct / 100))
                rec = _build_rec(
                    m, pop, "decrease", decrease_pct, new_price,
                    f"Very high margin ({margin_pct:.1f}%) but low demand. "
                    f"A small price drop could boost sales without hurting profitability.",
                    confidence=0.6,
                    priority="medium",
                )
            else:
                rec = _build_rec(
                    m, pop, "hold", 0, current_price,
                    f"Good margin ({margin_pct:.1f}%). Focus on increasing visibility "
                    f"through upselling — no price change needed.",
                    confidence=0.7,
                    priority="low",
                )

        else:
            # Star: everything is optimized
            rec = _build_rec(
                m, pop, "hold", 0, current_price,
                f"Star item ⭐ — high margin ({margin_pct:.1f}%) and popular. "
                f"Maintain quality and keep promoting.",
                confidence=0.9,
                priority="low",
            )

        recommendations.append(rec)

    # Sort: critical → high → medium → low
    priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    recommendations.sort(key=lambda r: priority_order.get(r["priority"], 99))

    return recommendations


def _build_rec(
    margin_data: dict,
    pop_data: dict,
    direction: str,
    change_pct: float,
    new_price: float,
    rationale: str,
    confidence: float,
    priority: str,
) -> dict:
    return {
        "item_id": margin_data["item_id"],
        "name": margin_data["name"],
        "category": margin_data["category"],
        "current_price": margin_data["selling_price"],
        "food_cost": margin_data["food_cost"],
        "current_margin_pct": margin_data["margin_pct"],
        "popularity_score": pop_data.get("popularity_score", 0),
        "direction": direction,  # increase | decrease | hold | review
        "change_pct": round(change_pct, 1),
        "recommended_price": new_price,
        "new_margin_pct": round(
            (new_price - margin_data["food_cost"]) / new_price * 100, 1
        ) if new_price > 0 else 0,
        "rationale": rationale,
        "confidence": confidence,
        "priority": priority,
    }


def _round_price(price: float) -> float:
    """Round to nearest ₹5 for clean pricing."""
    return round(price / 5) * 5
