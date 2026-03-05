"""
quantity_extractor.py — Quantity Extraction from Text
======================================================
Extracts quantities from natural language text,
handling both digit and word-form numbers in
English, Hindi, and Hinglish.
"""

import re


# Number words → digit mapping
NUMBER_WORDS = {
    # English
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "a": 1, "an": 1, "single": 1, "double": 2, "triple": 3,
    "half": 0.5,
    # Hindi (romanized)
    "ek": 1, "do": 2, "teen": 3, "char": 4, "paanch": 5,
    "chhe": 6, "saat": 7, "aath": 8, "nau": 9, "das": 10,
    # Hindi (Devanagari)
    "एक": 1, "दो": 2, "तीन": 3, "चार": 4, "पाँच": 5,
}

# Unit words that often follow quantities
UNIT_WORDS = {
    "plate", "plates", "piece", "pieces", "glass", "glasses",
    "cup", "cups", "bowl", "bowls", "serving", "servings",
    "portion", "portions", "order", "orders",
    # Hindi
    "plate", "pyaala", "gilaas", "piece",
}


def extract_quantities(text: str, matched_items: list[dict]) -> list[dict]:
    """
    Extract quantities for matched menu items from text.

    Handles patterns like:
    - "2 butter naan" → qty 2
    - "do plate paneer tikka" → qty 2
    - "ek butter chicken aur teen naan" → qty 1, 3
    - "paneer tikka" (no qty mentioned) → default qty 1

    Args:
        text: Normalized text
        matched_items: Items matched by item_matcher

    Returns:
        Items with 'quantity' field added
    """
    text_lower = text.lower()

    for item in matched_items:
        qty = _find_quantity_for_item(text_lower, item["name"].lower())
        item["quantity"] = qty

    return matched_items


def _find_quantity_for_item(text: str, item_name: str) -> int:
    """Find the quantity associated with a specific item in text."""
    # Try to find quantity near the item name
    words = text.split()
    item_words = item_name.split()

    # Find where the item name appears in text
    for i in range(len(words)):
        # Check if any item word matches here
        if any(fuzz_match(words[i], iw) for iw in item_words):
            # Look backwards for a number
            for j in range(max(0, i - 3), i):
                qty = _parse_number(words[j])
                if qty is not None:
                    return max(1, int(qty))

    # Fallback: look for any number in the entire text
    for word in words:
        qty = _parse_number(word)
        if qty is not None and len(matched_items_names(text)) == 1:
            return max(1, int(qty))

    # Default quantity
    return 1


def _parse_number(word: str) -> int | None:
    """Parse a word as a number (digit or word form)."""
    # Try digit
    try:
        return int(word)
    except ValueError:
        pass

    # Try number word
    if word in NUMBER_WORDS:
        return int(NUMBER_WORDS[word])

    return None


def fuzz_match(a: str, b: str) -> bool:
    """Simple check if two words are similar enough."""
    if a == b:
        return True
    if len(a) < 3 or len(b) < 3:
        return a == b
    # Simple character overlap check
    common = set(a) & set(b)
    return len(common) / max(len(set(a)), len(set(b))) > 0.6


def matched_items_names(text: str) -> list:
    """Placeholder — count how many distinct items in text."""
    return [text]  # simplified
