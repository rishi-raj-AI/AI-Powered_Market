from __future__ import annotations

CATEGORIES = [
    ("payment", {"payment", "charged", "refund", "upi", "cod", "money", "पेमेंट", "रिफंड"}),
    ("delivery", {"delivery", "rider", "late", "missing", "delivered", "डिलीवरी", "रायडर"}),
    ("order", {"order", "item", "wrong", "damaged", "quantity", "ऑर्डर", "सामान", "खराब"}),
    ("account", {"login", "otp", "account", "profile", "लॉगिन", "ओटीपी"}),
]
URGENT = {"fraud", "charged twice", "double charged", "unsafe", "threat", "accident", "medical"}
HIGH = {"not delivered", "late", "missing", "refund", "damaged", "wrong item", "cancelled but charged"}


def triage_ticket(subject: str, description: str) -> dict[str, str]:
    text = f"{subject} {description}".lower().strip()
    category = next((name for name, terms in CATEGORIES if any(term in text for term in terms)), "general")
    priority = "urgent" if any(term in text for term in URGENT) else "high" if any(term in text for term in HIGH) else "medium" if category in {"payment", "delivery"} else "normal"
    actions = {
        "payment": "Review payment attempt, provider events and settlement state; do not change financial state manually.",
        "delivery": "Review lifecycle, assignment, latest location and proof or failure evidence.",
        "order": "Review order items, merchant transitions and cancellation or refund eligibility.",
        "account": "Review authentication events without exposing OTPs or credentials.",
    }
    summary = description.strip().replace("\n", " ")[:500] or subject.strip()
    return {"category": category, "priority": priority, "summary": summary, "suggested_action": actions.get(category, "Review the customer context and route it to the responsible operator.")}
