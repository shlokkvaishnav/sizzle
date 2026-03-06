"""
normalizer.py — Text Normalization for Hindi/Hinglish/Gujarati/Marathi
=======================================================================
Supports: English, Hindi, Hinglish, Gujarati, Marathi
Only LINGUISTIC patterns are hardcoded (numbers, fillers).
Food/menu data comes from the DATABASE via item_matcher.
"""

import re

# ---------------------------------------------------------------------------
# Devanagari -> Romanized transliteration map (common restaurant words)
# Applied BEFORE number/filler processing so downstream stays Latin-script.
# ---------------------------------------------------------------------------
DEVANAGARI_MAP = {
    # Numbers
    "एक": "ek", "दो": "do", "तीन": "teen", "चार": "char",
    "पांच": "paanch", "पाँच": "paanch", "छह": "chhe", "छे": "chhe",
    "सात": "saat", "आठ": "aath", "नौ": "nau", "दस": "das",
    "ग्यारह": "gyarah", "बारह": "barah", "बीस": "bees",
    # Common ordering words
    "और": "aur", "या": "ya", "भी": "bhi",
    "दे": "de", "देना": "dena", "दो": "do",  # context: "give" vs "two" handled below
    "लाओ": "lao", "चाहिए": "chahiye", "चाहिये": "chahiye",
    "कृपया": "please", "प्लीज": "please",
    # Common fillers
    "भैया": "bhaiya", "भइया": "bhaiya", "भाई": "bhai",
    "यार": "yaar", "बॉस": "boss", "जी": "ji",
    "अच्छा": "accha", "ठीक": "theek", "हाँ": "haan", "हां": "haan",
    # Modifiers
    "एक्स्ट्रा": "extra", "बिना": "bina", "स्पाइसी": "spicy",
    "ज़्यादा": "zyada", "कम": "kam",
    # Common food words (helps fuzzy matching after transliteration)
    "पनीर": "paneer", "टिक्का": "tikka", "बटर": "butter",
    "नान": "naan", "रोटी": "roti", "चिकन": "chicken",
    "बिरयानी": "biryani", "दाल": "dal", "मसाला": "masala",
    "लस्सी": "lassi", "चाय": "chai", "गुलाब": "gulab",
    "जामुन": "jamun", "मखनी": "makhani", "मक्खनी": "makhani",
    "तंदूरी": "tandoori", "तन्दूरी": "tandoori",
    "पालक": "palak", "शाही": "shahi", "कड़ाही": "kadhai",
    "मटन": "mutton", "गोश्त": "gosht", "मछली": "fish",
    "आलू": "aloo", "गोभी": "gobhi", "भिंडी": "bhindi",
    "राइस": "rice", "चावल": "chawal", "खीर": "kheer",
    "रसमलाई": "rasmalai", "कुल्फी": "kulfi",
    "कोल्ड": "cold", "ड्रिंक": "drink", "पानी": "pani",
    "मशरूम": "mushroom", "केबाब": "kebab", "कबाब": "kebab",
    "रायता": "raita", "सलाद": "salad",
}


# ---------------------------------------------------------------------------
# Gujarati script -> Romanized transliteration map (common restaurant words)
# Unicode block: U+0A80 – U+0AFF
# ---------------------------------------------------------------------------
GUJARATI_MAP = {
    # Numbers
    "એક": "ek", "બે": "be", "ત્રણ": "tran", "ચાર": "char",
    "પાંચ": "paanch", "છ": "chhe", "સાત": "saat", "આઠ": "aath",
    "નવ": "nav", "દસ": "das",
    # Common ordering words
    "અને": "aur", "આપો": "de", "જોઈએ": "chahiye", "જોઇએ": "chahiye",
    "કર": "kar", "કરો": "karo", "દો": "do", "આપ": "aap",
    "હા": "haan", "ના": "nahi", "બસ": "bas", "ઓકે": "ok",
    "ચાલે": "chale", "ચાલશે": "chalse", "પ્લીઝ": "please",
    # Modifiers
    "એક્સ્ટ્રા": "extra", "વગર": "bina", "વધારે": "zyada", "ઓછું": "kam",
    # Common food words
    "પનીર": "paneer", "ટિક્કા": "tikka", "ટિકા": "tikka",
    "બટર": "butter", "નાન": "naan", "રોટી": "roti", "રોટલી": "roti",
    "ચિકન": "chicken", "બિરયાની": "biryani", "દાળ": "dal", "દાલ": "dal",
    "મસાલા": "masala", "લસ્સી": "lassi", "ચા": "chai", "ચાય": "chai",
    "ગુલાબ": "gulab", "જામુન": "jamun", "મખની": "makhani",
    "તંદૂરી": "tandoori", "પાલક": "palak", "શાહી": "shahi",
    "મટન": "mutton", "આલુ": "aloo", "આલૂ": "aloo",
    "ગોભી": "gobhi", "ગોબી": "gobhi", "ખીર": "kheer",
    "કુલ્ફી": "kulfi", "કોલ્ડ": "cold", "પાણી": "pani",
    "કબાબ": "kebab", "કેબાબ": "kebab", "રાયતા": "raita",
    "સલાડ": "salad", "મશરૂમ": "mushroom", "રાઈસ": "rice",
    # Gujarati-specific food
    "થેપલા": "thepla", "ઢોકળા": "dhokla", "ખાખરા": "khakhra",
    "ફાફડા": "fafda", "ઊંધિયું": "undhiyu", "જલેબી": "jalebi",
    "ગાંઠિયા": "gathiya", "ખાંડવી": "khandvi",
}

# ---------------------------------------------------------------------------
# Kannada script -> Romanized transliteration map (common restaurant words)
# Unicode block: U+0C80 – U+0CFF
# ---------------------------------------------------------------------------
KANNADA_MAP = {
    # Numbers
    "ಒಂದು": "ondu", "ಎರಡು": "eradu", "ಮೂರು": "mooru",
    "ನಾಲ್ಕು": "naalku", "ಐದು": "aidu",
    # Common ordering words
    "ಮತ್ತು": "mattu", "ಕೊಡಿ": "kodi", "ಬೇಕು": "beku",
    "ಹಾಕಿ": "haaki", "ಸೇರಿಸಿ": "serisi",
    "ಹೌದು": "houdu", "ಇಲ್ಲ": "illa", "ಸಾಕು": "saaku",
    # Common food words
    "ಪನೀರ್": "paneer", "ಪನೀರು": "paneer",
    "ಟಿಕ್ಕಾ": "tikka", "ಬಟರ್": "butter", "ನಾನ್": "naan",
    "ರೋಟಿ": "roti", "ಚಿಕನ್": "chicken", "ಚಿಕೆನ್": "chicken",
    "ಬಿರಿಯಾನಿ": "biryani", "ದಾಲ್": "dal",
    "ಮಸಾಲಾ": "masala", "ಲಸ್ಸಿ": "lassi", "ಚಹಾ": "chai",
    "ಗುಲಾಬ್": "gulab", "ಜಾಮೂನ್": "jamun",
    "ತಂದೂರಿ": "tandoori", "ಪಾಲಕ್": "palak",
    "ಮಟನ್": "mutton", "ಆಲೂ": "aloo", "ಕಬಾಬ್": "kebab",
    "ರೈಸ್": "rice", "ಅನ್ನ": "rice",
}


# ---------------------------------------------------------------------------
# Character-level Gujarati -> Roman transliteration (fallback)
# ---------------------------------------------------------------------------
_GUJ_VOWELS_INDEP = {
    '\u0A85': 'a', '\u0A86': 'aa', '\u0A87': 'i', '\u0A88': 'ee',
    '\u0A89': 'u', '\u0A8A': 'oo', '\u0A8F': 'e', '\u0A90': 'ai',
    '\u0A93': 'o', '\u0A94': 'au', '\u0A8B': 'ri',
}
_GUJ_MATRAS = {
    '\u0ABE': 'a', '\u0ABF': 'i', '\u0AC0': 'ee', '\u0AC1': 'u',
    '\u0AC2': 'oo', '\u0AC7': 'e', '\u0AC8': 'ai', '\u0ACB': 'o',
    '\u0ACC': 'au', '\u0AC3': 'ri',
}
_GUJ_CONSONANTS = {
    '\u0A95': 'k', '\u0A96': 'kh', '\u0A97': 'g', '\u0A98': 'gh', '\u0A99': 'ng',
    '\u0A9A': 'ch', '\u0A9B': 'chh', '\u0A9C': 'j', '\u0A9D': 'jh', '\u0A9E': 'ny',
    '\u0A9F': 't', '\u0AA0': 'th', '\u0AA1': 'd', '\u0AA2': 'dh', '\u0AA3': 'n',
    '\u0AA4': 't', '\u0AA5': 'th', '\u0AA6': 'd', '\u0AA7': 'dh', '\u0AA8': 'n',
    '\u0AAA': 'p', '\u0AAB': 'ph', '\u0AAC': 'b', '\u0AAD': 'bh', '\u0AAE': 'm',
    '\u0AAF': 'y', '\u0AB0': 'r', '\u0AB2': 'l', '\u0AB5': 'v',
    '\u0AB6': 'sh', '\u0AB7': 'sh', '\u0AB8': 's', '\u0AB9': 'h',
}
_GUJ_DIGITS = {
    '\u0AE6': '0', '\u0AE7': '1', '\u0AE8': '2', '\u0AE9': '3', '\u0AEA': '4',
    '\u0AEB': '5', '\u0AEC': '6', '\u0AED': '7', '\u0AEE': '8', '\u0AEF': '9',
}
_GUJ_HALANT = '\u0ACD'
_GUJ_NUKTA = '\u0ABC'
_GUJ_ANUSVARA = '\u0A82'
_GUJ_VISARGA = '\u0A83'


def _is_gujarati(c: str) -> bool:
    return '\u0A80' <= c <= '\u0AFF'


def _transliterate_remaining_gujarati(text: str) -> str:
    """Character-by-character Gujarati -> Roman transliteration with schwa deletion."""
    result = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if not _is_gujarati(c):
            result.append(c)
            i += 1
            continue
        if c in _GUJ_DIGITS:
            result.append(_GUJ_DIGITS[c])
            i += 1
            continue
        if i + 1 < n and text[i + 1] == _GUJ_NUKTA:
            base = _GUJ_CONSONANTS.get(c, '')
            i += 2
        elif c in _GUJ_CONSONANTS:
            base = _GUJ_CONSONANTS[c]
            i += 1
        elif c in _GUJ_VOWELS_INDEP:
            result.append(_GUJ_VOWELS_INDEP[c])
            i += 1
            continue
        elif c == _GUJ_ANUSVARA:
            result.append('n')
            i += 1
            continue
        elif c == _GUJ_VISARGA:
            result.append('h')
            i += 1
            continue
        else:
            i += 1
            continue
        # Consonant post-processing
        if i < n and text[i] == _GUJ_HALANT:
            result.append(base)
            i += 1
        elif i < n and text[i] in _GUJ_MATRAS:
            result.append(base + _GUJ_MATRAS[text[i]])
            i += 1
        else:
            at_word_end = (i >= n or not _is_gujarati(text[i]))
            result.append(base if at_word_end else base + 'a')
    return ''.join(result)


def _transliterate_gujarati(text: str) -> str:
    """Two-pass Gujarati transliteration: word-level then character-level."""
    for guj, roman in sorted(GUJARATI_MAP.items(), key=lambda x: len(x[0]), reverse=True):
        text = text.replace(guj, roman)
    text = _transliterate_remaining_gujarati(text)
    return text


# ---------------------------------------------------------------------------
# Character-level Kannada -> Roman transliteration (fallback)
# ---------------------------------------------------------------------------
_KAN_VOWELS_INDEP = {
    '\u0C85': 'a', '\u0C86': 'aa', '\u0C87': 'i', '\u0C88': 'ee',
    '\u0C89': 'u', '\u0C8A': 'oo', '\u0C8E': 'e', '\u0C8F': 'ee',
    '\u0C90': 'ai', '\u0C92': 'o', '\u0C93': 'oo', '\u0C94': 'au',
}
_KAN_MATRAS = {
    '\u0CBE': 'a', '\u0CBF': 'i', '\u0CC0': 'ee', '\u0CC1': 'u',
    '\u0CC2': 'oo', '\u0CC6': 'e', '\u0CC7': 'ee', '\u0CC8': 'ai',
    '\u0CCA': 'o', '\u0CCB': 'oo', '\u0CCC': 'au',
}
_KAN_CONSONANTS = {
    '\u0C95': 'k', '\u0C96': 'kh', '\u0C97': 'g', '\u0C98': 'gh', '\u0C99': 'ng',
    '\u0C9A': 'ch', '\u0C9B': 'chh', '\u0C9C': 'j', '\u0C9D': 'jh', '\u0C9E': 'ny',
    '\u0C9F': 't', '\u0CA0': 'th', '\u0CA1': 'd', '\u0CA2': 'dh', '\u0CA3': 'n',
    '\u0CA4': 't', '\u0CA5': 'th', '\u0CA6': 'd', '\u0CA7': 'dh', '\u0CA8': 'n',
    '\u0CAA': 'p', '\u0CAB': 'ph', '\u0CAC': 'b', '\u0CAD': 'bh', '\u0CAE': 'm',
    '\u0CAF': 'y', '\u0CB0': 'r', '\u0CB2': 'l', '\u0CB5': 'v',
    '\u0CB6': 'sh', '\u0CB7': 'sh', '\u0CB8': 's', '\u0CB9': 'h',
}
_KAN_DIGITS = {
    '\u0CE6': '0', '\u0CE7': '1', '\u0CE8': '2', '\u0CE9': '3', '\u0CEA': '4',
    '\u0CEB': '5', '\u0CEC': '6', '\u0CED': '7', '\u0CEE': '8', '\u0CEF': '9',
}
_KAN_HALANT = '\u0CCD'
_KAN_ANUSVARA = '\u0C82'
_KAN_VISARGA = '\u0C83'


def _is_kannada(c: str) -> bool:
    return '\u0C80' <= c <= '\u0CFF'


def _transliterate_remaining_kannada(text: str) -> str:
    """Character-by-character Kannada -> Roman transliteration with schwa deletion."""
    result = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if not _is_kannada(c):
            result.append(c)
            i += 1
            continue
        if c in _KAN_DIGITS:
            result.append(_KAN_DIGITS[c])
            i += 1
            continue
        if c in _KAN_CONSONANTS:
            base = _KAN_CONSONANTS[c]
            i += 1
        elif c in _KAN_VOWELS_INDEP:
            result.append(_KAN_VOWELS_INDEP[c])
            i += 1
            continue
        elif c == _KAN_ANUSVARA:
            result.append('n')
            i += 1
            continue
        elif c == _KAN_VISARGA:
            result.append('h')
            i += 1
            continue
        else:
            i += 1
            continue
        if i < n and text[i] == _KAN_HALANT:
            result.append(base)
            i += 1
        elif i < n and text[i] in _KAN_MATRAS:
            result.append(base + _KAN_MATRAS[text[i]])
            i += 1
        else:
            at_word_end = (i >= n or not _is_kannada(text[i]))
            result.append(base if at_word_end else base + 'a')
    return ''.join(result)


def _transliterate_kannada(text: str) -> str:
    """Two-pass Kannada transliteration: word-level then character-level."""
    for kan, roman in sorted(KANNADA_MAP.items(), key=lambda x: len(x[0]), reverse=True):
        text = text.replace(kan, roman)
    text = _transliterate_remaining_kannada(text)
    return text


# ---------------------------------------------------------------------------
# Character-level Devanagari → Roman transliteration
# Fallback for words NOT covered by the word-level DEVANAGARI_MAP above.
# Produces approximate romanizations that downstream fuzzy + semantic
# matching can resolve to correct menu items.
# ---------------------------------------------------------------------------
_DEV_VOWELS_INDEP = {
    '\u0905': 'a', '\u0906': 'aa', '\u0907': 'i', '\u0908': 'ee',
    '\u0909': 'u', '\u090A': 'oo', '\u090F': 'e', '\u0910': 'ai',
    '\u0913': 'o', '\u0914': 'au', '\u090B': 'ri',
}
_DEV_MATRAS = {
    '\u093E': 'a', '\u093F': 'i', '\u0940': 'ee', '\u0941': 'u',
    '\u0942': 'oo', '\u0947': 'e', '\u0948': 'ai', '\u094B': 'o',
    '\u094C': 'au', '\u0943': 'ri',
}
_DEV_CONSONANTS = {
    '\u0915': 'k', '\u0916': 'kh', '\u0917': 'g', '\u0918': 'gh', '\u0919': 'ng',
    '\u091A': 'ch', '\u091B': 'chh', '\u091C': 'j', '\u091D': 'jh', '\u091E': 'ny',
    '\u091F': 't', '\u0920': 'th', '\u0921': 'd', '\u0922': 'dh', '\u0923': 'n',
    '\u0924': 't', '\u0925': 'th', '\u0926': 'd', '\u0927': 'dh', '\u0928': 'n',
    '\u092A': 'p', '\u092B': 'ph', '\u092C': 'b', '\u092D': 'bh', '\u092E': 'm',
    '\u092F': 'y', '\u0930': 'r', '\u0932': 'l', '\u0935': 'v',
    '\u0936': 'sh', '\u0937': 'sh', '\u0938': 's', '\u0939': 'h',
}
_DEV_NUKTA_MAP = {
    '\u0915\u093C': 'q', '\u0916\u093C': 'kh', '\u0917\u093C': 'gh',
    '\u091C\u093C': 'z', '\u0921\u093C': 'r', '\u0922\u093C': 'rh',
    '\u092B\u093C': 'f',
}
_DEV_DIGITS = {
    '\u0966': '0', '\u0967': '1', '\u0968': '2', '\u0969': '3', '\u096A': '4',
    '\u096B': '5', '\u096C': '6', '\u096D': '7', '\u096E': '8', '\u096F': '9',
}
_HALANT = '\u094D'
_NUKTA_CHAR = '\u093C'
_ANUSVARA = '\u0902'
_CHANDRABINDU = '\u0901'
_VISARGA = '\u0903'


def _is_devanagari(c: str) -> bool:
    return '\u0900' <= c <= '\u097F'


def _transliterate_remaining_devanagari(text: str) -> str:
    """
    Character-by-character Devanagari → Roman transliteration.
    Uses word-final schwa deletion: last consonant in a Devanagari
    word (before space / non-Devanagari / end) omits inherent 'a'.
    """
    result = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        # Non-Devanagari: pass through
        if not _is_devanagari(c):
            result.append(c)
            i += 1
            continue
        # Devanagari digit
        if c in _DEV_DIGITS:
            result.append(_DEV_DIGITS[c])
            i += 1
            continue
        # Nukta-modified consonant (e.g. ज़ = ज + ़)
        base = None
        if i + 1 < n and text[i + 1] == _NUKTA_CHAR:
            combo = c + _NUKTA_CHAR
            base = _DEV_NUKTA_MAP.get(combo, _DEV_CONSONANTS.get(c, ''))
            i += 2
        elif c in _DEV_CONSONANTS:
            base = _DEV_CONSONANTS[c]
            i += 1
        elif c in _DEV_VOWELS_INDEP:
            result.append(_DEV_VOWELS_INDEP[c])
            i += 1
            continue
        elif c in (_ANUSVARA, _CHANDRABINDU):
            result.append('n')
            i += 1
            continue
        elif c == _VISARGA:
            result.append('h')
            i += 1
            continue
        else:
            i += 1            # skip unknown Devanagari marks
            continue

        # --- Consonant post-processing: halant / matra / inherent vowel ---
        if i < n and text[i] == _HALANT:
            result.append(base)        # halant suppresses inherent vowel
            i += 1
        elif i < n and text[i] in _DEV_MATRAS:
            result.append(base + _DEV_MATRAS[text[i]])
            i += 1
        else:
            # Word-final schwa deletion: omit inherent 'a' at end of
            # Devanagari word (next char is space / non-Devanagari / end)
            at_word_end = (i >= n or not _is_devanagari(text[i]))
            result.append(base if at_word_end else base + 'a')

    return ''.join(result)


def _transliterate_devanagari(text: str) -> str:
    """
    Two-pass Devanagari transliteration:
      1. Word-level: replace known words/phrases from DEVANAGARI_MAP
         (longest match first to prevent partial replacements)
      2. Character-level: transliterate any remaining Devanagari chars
    """
    # Pass 1 — word/phrase level (longest first to avoid partial matches)
    for dev, roman in sorted(DEVANAGARI_MAP.items(),
                             key=lambda x: len(x[0]), reverse=True):
        text = text.replace(dev, roman)
    # Pass 2 — character-level fallback for anything not in the map
    text = _transliterate_remaining_devanagari(text)
    return text


# ---------------------------------------------------------------------------
# Phonetic correction map — common Indian-accent / STT mishearings
# ---------------------------------------------------------------------------
# Applied AFTER Devanagari transliteration, BEFORE fuzzy matching.
# Maps whole-word phonetic variants to standard English food spellings.
# Only maps words that are clearly food-related; avoids overcorrecting.
PHONETIC_CORRECTIONS = {
    # Chicken variants
    "chikan": "chicken", "chiken": "chicken", "chikken": "chicken",
    "chikn": "chicken", "chickan": "chicken", "chikin": "chicken",
    "chkin": "chicken", "chickn": "chicken", "chekin": "chicken",
    "murgh": "chicken", "murg": "chicken",
    # Mutton variants
    "mutan": "mutton", "muton": "mutton", "muten": "mutton",
    "mattan": "mutton", "gosht": "mutton",
    # Paneer variants
    "paner": "paneer", "panir": "paneer", "pneer": "paneer",
    "pnir": "paneer", "panee": "paneer", "paneera": "paneer",
    # Biryani variants
    "biriyani": "biryani", "briyani": "biryani", "biryni": "biryani",
    "biriani": "biryani", "bryani": "biryani", "biriyanee": "biryani",
    # Naan variants
    "nan": "naan", "naaan": "naan",
    # Roti variants
    "rotee": "roti", "rooti": "roti", "rodi": "roti", "rodi": "roti",
    "rothi": "roti",
    # Tikka variants
    "tika": "tikka", "teeka": "tikka", "tikkah": "tikka",
    # Dal variants
    "daal": "dal", "dhal": "dal",
    # Kebab variants
    "kabab": "kebab", "kabob": "kebab", "kebob": "kebab",
    "kabeb": "kebab",
    # Masala variants
    "masale": "masala", "msala": "masala", "masla": "masala",
    # Curry variants
    "kari": "curry", "karri": "curry",
    # Lassi variants
    "lasi": "lassi", "lassee": "lassi",
    # Chai variants
    "chay": "chai", "chae": "chai",
    # Tandoori variants
    "tanduri": "tandoori", "tanduri": "tandoori", "tndoori": "tandoori",
    # Makhani variants
    "makhni": "makhani", "makni": "makhani", "makhane": "makhani",
    # Kulfi variants
    "kulfee": "kulfi",
}

_PHONETIC_RE = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in sorted(PHONETIC_CORRECTIONS, key=len, reverse=True)) + r")\b"
)


def _apply_phonetic_corrections(text: str) -> str:
    """Replace phonetic variants with standard food spellings (whole-word only)."""
    return _PHONETIC_RE.sub(lambda m: PHONETIC_CORRECTIONS[m.group(0)], text)


# Number words -> integer
# Covers Hindi, Gujarati, Marathi romanized variants
NUMBER_WORDS = {
    # Hindi / Hinglish
    "ek": 1, "ak": 1,
    "do": 2, "dono": 2, "dou": 2,
    "teen": 3, "tin": 3,
    "char": 4, "chaar": 4,
    "paanch": 5, "panch": 5,
    "chhe": 6, "chheh": 6,
    "saat": 7, "sat": 7,
    "aath": 8, "ath": 8,
    "nau": 9, "naw": 9,
    "das": 10,
    "gyarah": 11,
    "barah": 12,
    "tera": 13,
    "chaudah": 14,
    "pandrah": 15,
    "bees": 20,

    # Gujarati romanized
    "be": 2,
    "tran": 3,
    "chha": 6,
    "nav": 9,

    # Marathi romanized
    "don": 2,
    "paach": 5,
    "saha": 6,
    "daha": 10,

    # English number words
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}

# Conversational filler words across all 5 supported languages
FILLERS = {
    # English / common
    "umm", "uh", "uhh", "hmm", "aaa", "err", "please",
    "okay", "ok", "actually", "basically",
    # Hindi / Hinglish
    "bhai", "bhaiya", "bhaiyya", "bhaia", "yaar", "boss",
    "sunlo", "suniye", "suno",
    "bolo", "batao", "ji", "haan", "theek", "acha", "accha", "matlab",
    "dekho", "dekhiye", "sahab", "saab",
    # Gujarati
    "kem", "saro",
    # Marathi
    "arey", "bro", "na",
    # Hindi ordering verbs (transliterated from Devanagari)
    "karna", "karana", "karo", "kar",
    "dijiye", "kijiye", "banao", "lagao",
}


def normalize(text: str) -> str:
    """
    Input : raw Whisper transcript
    Output: cleaned lowercase string ready for intent + item parsing
    """
    if not text or not text.strip():
        return ""

    text = text.lower().strip()

    # Remove punctuation except spaces
    # Preserve Devanagari (U+0900-097F), Gujarati (U+0A80-0AFF),
    # and Kannada (U+0C80-0CFF) blocks so matras/vowel signs survive
    text = re.sub(r"[^\w\s\u0900-\u097F\u0A80-\u0AFF\u0C80-\u0CFF]", " ", text)

    # Transliterate all Indic scripts -> romanized BEFORE number/filler processing
    text = _transliterate_devanagari(text)
    text = _transliterate_gujarati(text)
    text = _transliterate_kannada(text)

    # Apply phonetic corrections for Indian-accent STT mishearings
    # e.g. "chikan" → "chicken", "biriyani" → "biryani"
    text = _apply_phonetic_corrections(text)

    # Replace number words with digits (Hindi, Gujarati, Marathi, English)
    tokens = text.split()
    tokens = [str(NUMBER_WORDS[t]) if t in NUMBER_WORDS else t for t in tokens]
    text = " ".join(tokens)

    # Remove filler words
    tokens = text.split()
    tokens = [t for t in tokens if t not in FILLERS]
    text = " ".join(tokens)

    # Collapse multiple spaces
    text = re.sub(r"\s+", " ", text).strip()

    return text
