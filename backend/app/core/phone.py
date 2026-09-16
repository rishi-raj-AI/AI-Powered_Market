import re


def normalize_indian_phone(value: str) -> str:
    """Return one canonical Indian mobile identity without guessing country codes."""
    digits = re.sub(r"[\s()\-]", "", value.strip())
    if digits.startswith("+"):
        digits = digits[1:]
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    if not re.fullmatch(r"[6-9]\d{9}", digits):
        raise ValueError("Enter a valid 10-digit Indian mobile number")
    return f"+91{digits}"
