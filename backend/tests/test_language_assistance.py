from app.services.language_assistance import catalog_assist_draft, ordering_intent_draft


def test_catalog_assistance_is_confirmation_only() -> None:
    draft = catalog_assist_draft(transcript="  तांदूळ   5 किलो  ", language="mr")
    assert draft.language == "mr"
    assert draft.normalized_text == "तांदूळ 5 किलो"
    assert draft.requires_merchant_confirmation is True


def test_voice_ordering_never_mutates_cart_or_places_order() -> None:
    intent = ordering_intent_draft(transcript="दो किलो चावल", language="hi")
    assert intent["language"] == "hi"
    assert intent["requires_user_confirmation"] is True
    assert intent["mutates_cart"] is False
    assert intent["places_order"] is False


def test_unsupported_language_falls_back_to_english_contract() -> None:
    draft = catalog_assist_draft(transcript="milk", language="xx")
    assert draft.language == "en"
