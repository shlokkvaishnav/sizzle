"""
pipeline.py — Voice Ordering Pipeline Orchestrator
====================================================
Runs the complete voice → order flow:
Audio → STT → Normalize → Intent → Match Items →
Extract Qty/Modifiers → Build Order → Suggest Upsell
"""

import logging
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from .stt import transcribe_audio
from .normalizer import normalize_text
from .intent_mapper import classify_intent
from .item_matcher import match_items
from .quantity_extractor import extract_quantities
from .modifier_extractor import extract_modifiers
from .upsell_engine import suggest_upsells
from .order_builder import build_order, generate_kot

logger = logging.getLogger("petpooja.voice")


def process_voice_order(
    db: Session,
    audio_path: Optional[str] = None,
    text_input: Optional[str] = None,
    session_id: Optional[str] = None,
) -> dict:
    """
    Process a voice order from audio or text input.

    Args:
        db: Database session for menu lookups
        audio_path: Path to audio file (WAV/MP3)
        text_input: Direct text input (skip STT)
        session_id: Order session ID

    Returns:
        Dict with parsed order, upsells, and KOT
    """
    result = {
        "session_id": session_id,
        "raw_text": "",
        "normalized_text": "",
        "intent": "",
        "matched_items": [],
        "order": None,
        "kot": None,
        "upsells": [],
        "errors": [],
    }

    # Step 1: STT (or use text input directly)
    if audio_path:
        try:
            raw_text = transcribe_audio(audio_path)
        except Exception as e:
            logger.error(f"STT failed: {e}")
            result["errors"].append(f"Speech recognition failed: {str(e)}")
            return result
    elif text_input:
        raw_text = text_input
    else:
        result["errors"].append("No audio or text input provided")
        return result

    result["raw_text"] = raw_text

    # Step 2: Normalize Hindi/Hinglish text
    normalized = normalize_text(raw_text)
    result["normalized_text"] = normalized

    # Step 3: Classify intent
    intent = classify_intent(normalized)
    result["intent"] = intent

    if intent not in ("order", "add", "modify"):
        # Non-ordering intents (greeting, query, etc.)
        return result

    # Step 4: Match against menu items
    matched = match_items(db, normalized)
    result["matched_items"] = matched

    if not matched:
        result["errors"].append("Could not match any menu items from input")
        return result

    # Step 5: Extract quantities
    items_with_qty = extract_quantities(normalized, matched)

    # Step 6: Extract modifiers (spice level, size, add-ons)
    items_with_mods = extract_modifiers(normalized, items_with_qty)

    # Step 7: Build order
    order = build_order(items_with_mods, session_id)
    result["order"] = order

    # Step 8: Generate KOT
    kot = generate_kot(order)
    result["kot"] = kot

    # Step 9: Suggest upsells
    ordered_item_ids = [item["item_id"] for item in items_with_mods]
    upsells = suggest_upsells(db, ordered_item_ids)
    result["upsells"] = upsells

    return result
