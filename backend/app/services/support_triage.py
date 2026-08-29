from __future__ import annotations


CATEGORY_RULES = [
    ("payment", {"payment", "paid", "charged", "refund", "upi", "cod", "money", "पैसे", "पेमेंट", "रिफंड"}),
    ("delivery", {"delivery", "rider", "late", "delay", "missing", "delivered", "डिलीवरी", "रायडर", "उशीर", "देर"}),
    ("order", {"order", "item", "wrong", "damaged", "quantity", "ऑर्डर", "सामान", "गलत", "तुटले", "खराब"}),
    ("account", {"login", "otp", "account", "profile", "लॉगिन", "ओटीपी"}),
]

URGENT_TERMS = {
    "fraud", "charged twice", "double charged", "unsafe", "threat", "accident", "medical",
    "missing money", "wrong payment", "फ्रॉड", "दोनदा पैसे", "दो बार पैसे", "धोखा",
}

HIGH_TERMS = {
    "not delivered", "late", "missing", "refund", "damaged", "wrong item", "cancelled but charged",
    "डिलीवरी नाही", "उशीर", "रिफंड", "खराब", "गलत सामान",
}


def triage_ticket(subject: str, description: str) -> dict:
    text = f"{subject} {description}".lower().strip()
    category = "general"
    for candidate, terms in CATEGORY_RULES:
        if any(term in text for term in terms):
            category = candidate
            break

    if any(term in text for term in URGENT_TERMS):
        priority = "urgent"
    elif any(term in text for term in HIGH_TERMS):
        priority = "high"
    elif category in {"payment", "delivery"}:
        priority = "medium"
    else:
        priority = "normal"

    if category == "payment":
        action = "Review payment attempt, webhook history and settlement state before contacting the customer."
    elif category == "delivery":
        action = "Review delivery lifecycle, assignment, latest location and proof/failure evidence."
    elif category == "order":
        action = "Review order items, merchant transition history and any cancellation/refund eligibility."
    elif category == "account":
        action = "Review authentication/session events without exposing OTP or credential secrets."
    else:
        action = "Review the customer context and route to the appropriate operations owner."

    summary = description.strip().replace("\n", " ")
    if len(summary) > 420:
        summary = summary[:417] + "..."
    return {
        "category": category,
        "priority": priority,
        "summary": summary or subject.strip(),
        "suggested_action": action,
        "method": "deterministic_support_triage_v1",
    }
