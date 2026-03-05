"""
routes_revenue.py — Revenue Intelligence API Endpoints
========================================================
/api/revenue/* — Menu analysis, BCG matrix, combos, pricing
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from modules.revenue.analyzer import run_full_analysis
from modules.revenue.contribution_margin import calculate_margins
from modules.revenue.popularity import calculate_popularity
from modules.revenue.menu_matrix import classify_menu_matrix, get_quadrant_summary
from modules.revenue.hidden_stars import detect_hidden_stars
from modules.revenue.combo_engine import generate_combos
from modules.revenue.price_optimizer import generate_price_recommendations

router = APIRouter()


@router.get("/analyze")
def full_analysis(db: Session = Depends(get_db)):
    """Run the complete revenue intelligence pipeline."""
    return run_full_analysis(db)


@router.get("/margins")
def get_margins(db: Session = Depends(get_db)):
    """Get contribution margins for all items."""
    return {"items": calculate_margins(db)}


@router.get("/popularity")
def get_popularity(db: Session = Depends(get_db)):
    """Get popularity/velocity scores for all items."""
    return {"items": calculate_popularity(db)}


@router.get("/matrix")
def get_menu_matrix(db: Session = Depends(get_db)):
    """Get BCG matrix classification."""
    margins = calculate_margins(db)
    popularity = calculate_popularity(db)
    matrix = classify_menu_matrix(margins, popularity)
    summary = get_quadrant_summary(matrix)
    return {"items": matrix, "summary": summary}


@router.get("/hidden-stars")
def get_hidden_stars(db: Session = Depends(get_db)):
    """Get hidden star items (high CM, low visibility)."""
    margins = calculate_margins(db)
    popularity = calculate_popularity(db)
    return {"items": detect_hidden_stars(margins, popularity)}


@router.get("/combos")
def get_combo_suggestions(db: Session = Depends(get_db)):
    """Get AI-generated combo recommendations."""
    return {"combos": generate_combos(db)}


@router.get("/pricing")
def get_price_recommendations(db: Session = Depends(get_db)):
    """Get rule-based price optimization recommendations."""
    margins = calculate_margins(db)
    popularity = calculate_popularity(db)
    return {"recommendations": generate_price_recommendations(margins, popularity)}
