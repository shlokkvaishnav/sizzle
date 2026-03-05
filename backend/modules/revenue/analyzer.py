"""
analyzer.py — Revenue Analysis Orchestrator
=============================================
Main entry point that calls all sub-modules and assembles
the complete revenue intelligence report.
"""

from sqlalchemy.orm import Session

from .contribution_margin import calculate_margins
from .popularity import calculate_popularity
from .menu_matrix import classify_menu_matrix
from .hidden_stars import detect_hidden_stars
from .combo_engine import generate_combos
from .price_optimizer import generate_price_recommendations


def run_full_analysis(db: Session) -> dict:
    """
    Run the complete revenue intelligence pipeline.

    Returns a dict with:
    - margins: per-item CM and margin %
    - popularity: per-item velocity and popularity scores
    - matrix: BCG quadrant classification
    - hidden_stars: high-CM, low-visibility items
    - combos: association-rule combo suggestions
    - price_recommendations: rule-based price nudges
    - summary: overall menu health metrics
    """
    # Step 1: Contribution margins
    margins = calculate_margins(db)

    # Step 2: Popularity / velocity
    popularity = calculate_popularity(db)

    # Step 3: BCG matrix classification (needs both margins + popularity)
    matrix = classify_menu_matrix(margins, popularity)

    # Step 4: Hidden star detection
    hidden_stars = detect_hidden_stars(margins, popularity)

    # Step 5: Combo recommendations (association rules)
    combos = generate_combos(db)

    # Step 6: Price optimization
    price_recs = generate_price_recommendations(margins, popularity)

    # Summary metrics
    total_items = len(margins)
    avg_margin = (
        sum(m["margin_pct"] for m in margins) / total_items
        if total_items > 0
        else 0
    )
    stars_count = sum(1 for m in matrix if m["quadrant"] == "star")
    dogs_count = sum(1 for m in matrix if m["quadrant"] == "dog")

    health_score = min(
        100,
        max(0, 50 + (avg_margin - 60) * 1.5 + stars_count * 3 - dogs_count * 5),
    )

    return {
        "margins": margins,
        "popularity": popularity,
        "matrix": matrix,
        "hidden_stars": hidden_stars,
        "combos": combos,
        "price_recommendations": price_recs,
        "summary": {
            "total_items": total_items,
            "avg_margin_pct": round(avg_margin, 1),
            "health_score": round(health_score, 1),
            "stars": stars_count,
            "dogs": dogs_count,
            "hidden_stars_count": len(hidden_stars),
            "combos_suggested": len(combos),
            "price_actions": sum(
                1 for p in price_recs if p["direction"] != "hold"
            ),
        },
    }
