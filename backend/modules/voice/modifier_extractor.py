"""
modifier_extractor.py — Spice/Size/Add-on Extraction
======================================================
Extracts modifiers from natural language:
- Spice level (mild, medium, spicy, extra spicy)
- Size (half, full, regular, large)
- Add-ons (extra cheese, no onion, less oil)
"""

import re


# Modifier patterns
SPICE_LEVELS = {
    "mild": ["mild", "kam teekha", "halka", "light spice", "कम तीखा"],
    "medium": ["medium", "normal", "regular spice", "thoda teekha"],
    "spicy": ["spicy", "teekha", "mirchi", "तीखा", "hot"],
    "extra_spicy": ["extra spicy", "bohot teekha", "bahut teekha", "बहुत तीखा", "very spicy"],
}

SIZE_MODIFIERS = {
    "half": ["half", "aadha", "आधा", "half plate"],
    "full": ["full", "poora", "पूरा", "full plate"],
    "regular": ["regular", "normal"],
    "large": ["large", "bada", "बड़ा", "extra large"],
}

ADD_ONS = {
    "extra_cheese": ["extra cheese", "cheese extra", "zyada cheese"],
    "no_onion": ["no onion", "bina pyaaz", "without onion", "बिना प्याज़"],
    "no_garlic": ["no garlic", "bina lahsun", "without garlic"],
    "less_oil": ["less oil", "kam tel", "कम तेल", "light oil"],
    "extra_butter": ["extra butter", "zyada butter", "butter extra"],
    "no_cream": ["no cream", "bina cream", "without cream"],
    "extra_gravy": ["extra gravy", "zyada gravy", "more gravy"],
    "dry": ["dry", "sukha", "सूखा", "without gravy"],
}

SPECIAL_INSTRUCTIONS = {
    "jaldi": "Prepare quickly / rush order",
    "pack": "Pack for takeaway",
    "parcel": "Pack for takeaway",
    "jain": "Jain preparation (no onion/garlic/root vegs)",
    "sugar_free": "No sugar",
}


def extract_modifiers(text: str, items: list[dict]) -> list[dict]:
    """
    Extract modifiers from text and attach to each item.

    Args:
        text: Normalized text
        items: Matched items with quantities

    Returns:
        Items with 'modifiers' field added
    """
    text_lower = text.lower()

    # Global modifiers (apply to all items if not item-specific)
    global_spice = _detect_spice(text_lower)
    global_size = _detect_size(text_lower)
    global_addons = _detect_addons(text_lower)
    special = _detect_special(text_lower)

    for item in items:
        modifiers = {
            "spice_level": global_spice,
            "size": global_size,
            "add_ons": global_addons.copy(),
            "special_instructions": special,
        }
        item["modifiers"] = modifiers

    return items


def _detect_spice(text: str) -> str:
    """Detect spice level from text."""
    for level, keywords in SPICE_LEVELS.items():
        for kw in keywords:
            if kw in text:
                return level
    return "medium"  # default


def _detect_size(text: str) -> str:
    """Detect size modifier from text."""
    for size, keywords in SIZE_MODIFIERS.items():
        for kw in keywords:
            if kw in text:
                return size
    return "regular"  # default


def _detect_addons(text: str) -> list[str]:
    """Detect add-on modifiers from text."""
    addons = []
    for addon_key, keywords in ADD_ONS.items():
        for kw in keywords:
            if kw in text:
                addons.append(addon_key)
                break
    return addons


def _detect_special(text: str) -> str:
    """Detect special instructions from text."""
    instructions = []
    for keyword, instruction in SPECIAL_INSTRUCTIONS.items():
        if keyword in text:
            instructions.append(instruction)
    return "; ".join(instructions) if instructions else ""
