"""
intent_mapper.py — Intent Classification
==========================================
Classifies the intent of a customer utterance.
Rule-based, no external models required.
"""

import re


# Intent keywords mapped to intent types
INTENT_PATTERNS = {
    "order": [
        r"\b(chahiye|de do|dedo|laga do|order|want|give me|i'll have|i will have|get me)\b",
        r"\b(\d+)\s+(plate|piece|glass|cup|bowl|serving)\b",
    ],
    "add": [
        r"\b(aur|and|also|plus|extra|ek aur|one more|add)\b",
    ],
    "remove": [
        r"\b(hata do|remove|cancel|nahi|no|don't want|nikaal do)\b",
    ],
    "modify": [
        r"\b(change|badal|modify|instead|replace|swap)\b",
    ],
    "query": [
        r"\b(kya hai|what is|price|kitna|how much|menu|available|hai kya)\b",
    ],
    "confirm": [
        r"\b(confirm|done|bas|that's it|theek hai|ok|order kar do|bill)\b",
    ],
    "greeting": [
        r"\b(hello|hi|namaste|good morning|good evening|hey)\b",
    ],
}


def classify_intent(text: str) -> str:
    """
    Classify the intent of a customer utterance.

    Args:
        text: Normalized text from the customer

    Returns:
        Intent string: order | add | remove | modify | query | confirm | greeting | unknown
    """
    if not text:
        return "unknown"

    text_lower = text.lower()

    # Score each intent
    scores = {}
    for intent, patterns in INTENT_PATTERNS.items():
        score = 0
        for pattern in patterns:
            matches = re.findall(pattern, text_lower)
            score += len(matches)
        if score > 0:
            scores[intent] = score

    if not scores:
        # Default: if text contains food-like words, assume ordering
        if _contains_food_words(text_lower):
            return "order"
        return "unknown"

    # Return highest-scoring intent
    return max(scores, key=scores.get)


def _contains_food_words(text: str) -> bool:
    """Check if text contains common food-related words."""
    food_words = [
        "paneer", "chicken", "dal", "naan", "roti", "biryani",
        "rice", "chai", "coffee", "lassi", "curry", "tikka",
        "butter", "masala", "kebab", "paratha", "kulfi",
        "gulab", "jamun", "raita", "salad",
        # Hindi food words
        "चिकन", "पनीर", "दाल", "नान", "बिरयानी", "चाय",
    ]
    return any(word in text for word in food_words)
