"""
menu_matrix.py — BCG Quadrant Classification
==============================================
Classifies menu items into the 4 BCG quadrants:
  ⭐ Stars       — High popularity, High margin
  🐴 Plowhorses  — High popularity, Low margin
  🧩 Puzzles     — Low popularity, High margin
  🐕 Dogs        — Low popularity, Low margin
"""


def classify_menu_matrix(
    margins: list[dict],
    popularity: list[dict],
    margin_threshold: float = 60.0,
    popularity_threshold: float = 0.4,
) -> list[dict]:
    """
    Classify items into BCG quadrants.

    Args:
        margins: Output of calculate_margins()
        popularity: Output of calculate_popularity()
        margin_threshold: Margin % cutoff for high/low
        popularity_threshold: Popularity score cutoff (0–1)

    Returns:
        List of items with quadrant classification
    """
    # Build lookup maps
    pop_map = {p["item_id"]: p for p in popularity}

    results = []
    for m in margins:
        item_id = m["item_id"]
        pop = pop_map.get(item_id, {})

        margin_pct = m.get("margin_pct", 0)
        pop_score = pop.get("popularity_score", 0)

        # Classify
        high_margin = margin_pct >= margin_threshold
        high_pop = pop_score >= popularity_threshold

        if high_margin and high_pop:
            quadrant = "star"
            emoji = "⭐"
            action = "Protect and promote. Keep quality consistent."
        elif not high_margin and high_pop:
            quadrant = "plowhorse"
            emoji = "🐴"
            action = "Increase price gradually or reduce portion cost."
        elif high_margin and not high_pop:
            quadrant = "puzzle"
            emoji = "🧩"
            action = "Boost visibility — feature in specials, train staff to upsell."
        else:
            quadrant = "dog"
            emoji = "🐕"
            action = "Consider removing or reworking the recipe."

        results.append({
            "item_id": item_id,
            "name": m["name"],
            "name_hi": m.get("name_hi", ""),
            "category": m["category"],
            "selling_price": m["selling_price"],
            "food_cost": m["food_cost"],
            "margin_pct": margin_pct,
            "popularity_score": pop_score,
            "daily_velocity": pop.get("daily_velocity", 0),
            "quadrant": quadrant,
            "emoji": emoji,
            "action": action,
            "is_veg": m.get("is_veg", True),
        })

    return results


def get_quadrant_summary(matrix: list[dict]) -> dict:
    """Get count and items per quadrant."""
    summary = {
        "star": {"count": 0, "items": []},
        "plowhorse": {"count": 0, "items": []},
        "puzzle": {"count": 0, "items": []},
        "dog": {"count": 0, "items": []},
    }
    for item in matrix:
        q = item["quadrant"]
        summary[q]["count"] += 1
        summary[q]["items"].append(item["name"])

    return summary
