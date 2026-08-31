from __future__ import annotations

import re
from dataclasses import dataclass

SUPPORTED_LANGUAGES = {"en", "hi", "mr"}


@dataclass(frozen=True)
class CatalogAssistDraft:
    language: str
    normalized_text: str
    suggested_name: str | None
    requires_merchant_confirmation: bool = True


def normalize_voice_transcript(text: str) -> str:
    """Normalize speech-to-text output without treating it as an order or catalog mutation."""
    return re.sub(r"\s+", " ", text.strip())


def catalog_assist_draft(*, transcript: str, language: str) -> CatalogAssistDraft:
    lang = language.lower().strip()
    if lang not in SUPPORTED_LANGUAGES:
        lang = "en"
    normalized = normalize_voice_transcript(transcript)
    suggestion = normalized[:180] if normalized else None
    return CatalogAssistDraft(
        language=lang,
        normalized_text=normalized,
        suggested_name=suggestion,
        requires_merchant_confirmation=True,
    )


def ordering_intent_draft(*, transcript: str, language: str) -> dict:
    """Return read-only intent input. Checkout/cart mutation remains explicit and backend-authoritative."""
    draft = catalog_assist_draft(transcript=transcript, language=language)
    return {
        "language": draft.language,
        "query": draft.normalized_text,
        "requires_user_confirmation": True,
        "mutates_cart": False,
        "places_order": False,
    }
