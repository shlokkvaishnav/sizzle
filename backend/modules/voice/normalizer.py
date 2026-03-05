"""
normalizer.py — Hindi/Hinglish Text Normalization
===================================================
Cleans and normalizes transcribed text for better
intent parsing and menu item matching.
"""

import re
import unicodedata


# Common Hindi/Hinglish food-related corrections
CORRECTIONS = {
    # English misspellings
    "panner": "paneer",
    "panneer": "paneer",
    "panir": "paneer",
    "naan": "naan",
    "nan": "naan",
    "roti": "roti",
    "rotee": "roti",
    "biryani": "biryani",
    "biriyani": "biryani",
    "bryani": "biryani",
    "daal": "dal",
    "dhal": "dal",
    "chiken": "chicken",
    "chikn": "chicken",
    "muton": "mutton",
    "matton": "mutton",
    "gobhi": "gobi",

    # Hinglish transliteration variants
    "ek": "1",
    "do": "2",
    "teen": "3",
    "char": "4",
    "paanch": "5",

    # Common ordering phrases
    "dedo": "de do",
    "dedijiye": "de dijiye",
    "chahiye": "chahiye",
    "lagado": "laga do",
    "bana do": "bana do",
    "aur": "and",
}

# Noise words to remove (filler words from speech)
NOISE_WORDS = {
    "umm", "uh", "hmm", "aa", "aah", "err", "like",
    "actually", "basically", "so", "well", "you know",
}


def normalize_text(text: str) -> str:
    """
    Normalize transcribed Hindi/Hinglish/English text.

    Steps:
    1. Unicode normalization
    2. Lowercase
    3. Remove punctuation (keep Devanagari)
    4. Fix common misspellings
    5. Remove filler/noise words
    6. Collapse whitespace
    """
    if not text or not text.strip():
        return ""

    # Unicode normalize
    text = unicodedata.normalize("NFKC", text)

    # Lowercase (only Latin chars, Devanagari is case-insensitive)
    text = text.lower()

    # Remove punctuation except Devanagari characters
    text = re.sub(r"[^\w\s\u0900-\u097F]", " ", text)

    # Apply corrections
    words = text.split()
    corrected = []
    for word in words:
        if word in NOISE_WORDS:
            continue
        corrected.append(CORRECTIONS.get(word, word))

    text = " ".join(corrected)

    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()

    return text


def transliterate_hindi_numbers(text: str) -> str:
    """Convert Hindi number words to digits."""
    hindi_nums = {
        "एक": "1", "दो": "2", "तीन": "3", "चार": "4",
        "पाँच": "5", "छह": "6", "सात": "7", "आठ": "8",
        "नौ": "9", "दस": "10",
    }
    for hindi, digit in hindi_nums.items():
        text = text.replace(hindi, digit)
    return text
