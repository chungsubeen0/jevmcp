"""Money rounding at invoice boundaries."""

from decimal import Decimal


def round_money(value: str | int | float | Decimal) -> Decimal:
    """Return *value* rounded to two currency places."""
    return Decimal(str(round(float(value), 2)))
