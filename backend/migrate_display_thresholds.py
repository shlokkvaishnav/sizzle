"""
migrate_display_thresholds.py
=============================
Adds the display_thresholds JSON column to the restaurant_settings table
for existing databases. Safe to run multiple times (checks first).

Usage:
    python migrate_display_thresholds.py
"""

import logging
from sqlalchemy import text
from database import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_THRESHOLDS = {
    "cm_green_min": 65,
    "cm_yellow_min": 50,
    "risk_margin_max": 40,
    "risk_popularity_min": 0.5,
    "confidence_green_min": 80,
    "confidence_yellow_min": 60,
}


def migrate():
    with engine.connect() as conn:
        # Check if column already exists
        result = conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'restaurant_settings' AND column_name = 'display_thresholds'"
        ))
        if result.fetchone():
            logger.info("display_thresholds column already exists — skipping.")
            return

        logger.info("Adding display_thresholds column to restaurant_settings...")
        conn.execute(text(
            "ALTER TABLE restaurant_settings ADD COLUMN display_thresholds JSONB DEFAULT '{}'"
        ))
        conn.commit()
        logger.info("Column added successfully.")

        # Backfill existing rows with default thresholds
        import json
        conn.execute(text(
            "UPDATE restaurant_settings SET display_thresholds = :val WHERE display_thresholds IS NULL OR display_thresholds = '{}'"
        ), {"val": json.dumps(DEFAULT_THRESHOLDS)})
        conn.commit()
        logger.info("Backfilled existing rows with default thresholds.")


if __name__ == "__main__":
    migrate()
