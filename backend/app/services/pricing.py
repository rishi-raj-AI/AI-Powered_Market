from decimal import Decimal


DELIVERY_FEE = Decimal("20.00")
MONEY_QUANTUM = Decimal("0.01")


def delivery_fee(*, serviceable: bool) -> Decimal:
    """Return the authoritative delivery fee for the current checkout contract."""
    return DELIVERY_FEE if serviceable else Decimal("0.00")


def checkout_totals(*, subtotal: Decimal, serviceable: bool) -> tuple[Decimal, Decimal]:
    """Return (delivery_fee, total) using one backend pricing authority."""
    fee = delivery_fee(serviceable=serviceable)
    return fee.quantize(MONEY_QUANTUM), (subtotal + fee).quantize(MONEY_QUANTUM)
