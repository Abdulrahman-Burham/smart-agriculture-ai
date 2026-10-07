"""Arabic text normalisation and light tokenisation used for lexical matching."""
from __future__ import annotations

import re

_DIACRITICS = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED\u0640]")
_ALEF = re.compile("[إأآٱ]")
_WS = re.compile(r"\s+")
_TOKEN = re.compile(r"\w+(?:\.\d+)?", re.UNICODE)
_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹٫", "01234567890123456789.")
_PREFIXES = ("وال", "بال", "كال", "فال", "لل", "ال")

_STOPWORDS = frozenset(
    "في من علي الي الى عن ان انا انت هو هي هم ما ماذا ده دي دا ايه اي كل قد كام لو مع او و "
    "بتاع بتاعي هل يا لا مش ممكن عندي عندك هذا هذه ذلك التي الذي على إلى".split()
)


def strip_diacritics(text: str) -> str:
    return _DIACRITICS.sub("", text)


def normalize_arabic(text: str) -> str:
    """Canonical form for matching: no diacritics/tatweel, unified alef/ya/ta-marbuta, ASCII digits."""
    text = strip_diacritics(text).translate(_DIGITS).lower()
    text = _ALEF.sub("ا", text).replace("ى", "ي").replace("ة", "ه")
    return _WS.sub(" ", text).strip()


def light_stem(token: str) -> str:
    for prefix in _PREFIXES:
        if token.startswith(prefix) and len(token) - len(prefix) >= 3:
            return token[len(prefix):]
    return token


def tokenize(text: str, *, drop_stopwords: bool = True) -> list[str]:
    tokens = [light_stem(t) for t in _TOKEN.findall(normalize_arabic(text))]
    if drop_stopwords:
        tokens = [t for t in tokens if t not in _STOPWORDS and len(t) > 1]
    return tokens
