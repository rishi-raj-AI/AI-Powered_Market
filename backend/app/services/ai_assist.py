from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable


LANG_HINTS = {
    "en": {"milk", "rice", "oil", "sugar", "salt", "tomato", "onion", "potato", "bread", "egg", "eggs"},
    "hi": {"दूध", "चावल", "तेल", "चीनी", "नमक", "टमाटर", "प्याज", "आलू", "अंडा", "अंडे"},
    "mr": {"दूध", "तांदूळ", "तेल", "साखर", "मीठ", "टोमॅटो", "कांदा", "बटाटा", "अंडे"},
}

CANONICAL_TERMS = {
    "दूध": "milk",
    "तांदूळ": "rice",
    "चावल": "rice",
    "तेल": "oil",
    "साखर": "sugar",
    "चीनी": "sugar",
    "मीठ": "salt",
    "नमक": "salt",
    "टोमॅटो": "tomato",
    "टमाटर": "tomato",
    "कांदा": "onion",
    "प्याज": "onion",
    "बटाटा": "potato",
    "आलू": "potato",
    "अंडे": "eggs",
    "अंडा": "eggs",
}

UNIT_HINTS = {
    "kg": "kg",
    "किलो": "kg",
    "किलोग्राम": "kg",
    "g": "g",
    "gram": "g",
    "grams": "g",
    "gm": "g",
    "ग्रॅम": "g",
    "ग्राम": "g",
    "l": "l",
    "litre": "l",
    "liter": "l",
    "लिटर": "l",
    "लीटर": "l",
    "ml": "ml",
    "मिली": "ml",
    "मिलि": "ml",
    "piece": "piece",
    "pieces": "piece",
    "pcs": "piece",
    "packet": "packet",
    "pack": "packet",
}

CATEGORY_HINTS = {
    "milk": "dairy",
    "curd": "dairy",
    "paneer": "dairy",
    "rice": "grocery",
    "oil": "grocery",
    "sugar": "grocery",
    "salt": "grocery",
    "tomato": "vegetables",
    "onion": "vegetables",
    "potato": "vegetables",
    "eggs": "dairy",
    "bread": "bakery",
    "cement": "hardware",
    "paint": "hardware",
    "seed": "agriculture",
    "fertilizer": "agriculture",
}

STOP_WORDS = {
    "i", "want", "need", "please", "give", "me", "add", "order", "buy",
    "मुझे", "चाहिए", "देना", "दो", "ऑर्डर", "करो", "मला", "हवे", "हवा", "द्या", "ऑर्डर",
}


@dataclass(frozen=True)
class ParsedItem:
    query: str
    quantity: float | None
    unit: str | None


def detect_language(text: str, requested: str | None = None) -> str:
    if requested in {"en", "hi", "mr"}:
        return requested
    devanagari = sum("\u0900" <= ch <= "\u097f" for ch in text)
    if devanagari == 0:
        return "en"
    marathi_markers = {"मला", "हवे", "हवा", "द्या", "कांदा", "बटाटा", "तांदूळ", "साखर", "मीठ"}
    tokens = set(text.split())
    return "mr" if tokens & marathi_markers else "hi"


def _normalized_tokens(text: str) -> list[str]:
    clean = re.sub(r"[^\w\u0900-\u097f.]+", " ", text.lower()).strip()
    return [token for token in clean.split() if token]


def _canonical(token: str) -> str:
    return CANONICAL_TERMS.get(token, token)


def parse_order_intent(text: str, language: str | None = None) -> dict:
    detected = detect_language(text, language)
    tokens = _normalized_tokens(text)
    quantity: float | None = None
    unit: str | None = None
    query_tokens: list[str] = []

    for token in tokens:
        canonical = _canonical(token)
        if quantity is None:
            try:
                quantity = float(token)
                continue
            except ValueError:
                pass
        if canonical in UNIT_HINTS:
            unit = UNIT_HINTS[canonical]
            continue
        if token in UNIT_HINTS:
            unit = UNIT_HINTS[token]
            continue
        if token in STOP_WORDS or canonical in STOP_WORDS:
            continue
        query_tokens.append(canonical)

    query = " ".join(dict.fromkeys(query_tokens)).strip()
    confidence = "high" if query and (quantity is not None or unit is not None) else "medium" if query else "low"
    return {
        "language": detected,
        "normalized_text": " ".join(tokens),
        "items": [{"query": query, "quantity": quantity or 1.0, "unit": unit}] if query else [],
        "confidence": confidence,
        "requires_confirmation": confidence != "high",
    }


def catalog_draft(name: str, description: str | None = None, language: str | None = None) -> dict:
    source = " ".join(part for part in [name, description or ""] if part).strip()
    detected = detect_language(source, language)
    tokens = [_canonical(token) for token in _normalized_tokens(source)]
    meaningful = [token for token in tokens if token not in STOP_WORDS]
    normalized_name = " ".join(word.capitalize() if word.isascii() else word for word in _normalized_tokens(name)).strip()

    category = None
    for token in meaningful:
        if token in CATEGORY_HINTS:
            category = CATEGORY_HINTS[token]
            break

    unit = None
    for token in tokens:
        if token in UNIT_HINTS:
            unit = UNIT_HINTS[token]
            break

    keywords = list(dict.fromkeys(token for token in meaningful if len(token) > 1))[:12]
    return {
        "language": detected,
        "normalized_name": normalized_name or name.strip(),
        "category_hint": category,
        "unit_hint": unit,
        "search_keywords": keywords,
        "description_draft": (description or name).strip(),
        "requires_merchant_review": True,
    }


def compact_keywords(values: Iterable[str], limit: int = 12) -> list[str]:
    output: list[str] = []
    for value in values:
        for token in _normalized_tokens(value):
            canonical = _canonical(token)
            if canonical not in STOP_WORDS and canonical not in output:
                output.append(canonical)
            if len(output) >= limit:
                return output
    return output
