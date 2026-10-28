"""A tiny inventory module for Steward to work on. It has a bug that test_inventory.py catches."""

from dataclasses import dataclass


@dataclass
class Item:
    name: str
    unit_price: float
    quantity: int


def order_total(items: list[Item], discount_percent: float = 0.0) -> float:
    """Total price of an order after a percentage discount, rounded to cents.
    ``discount_percent`` is expected as a percent (e.g. ``10`` for ten percent).
    The original implementation mistakenly treated the value as a fractional
    discount (e.g. ``0.10``).  The tests provide integer percentages, so we
    divide by 100 to obtain the correct multiplier."""
    subtotal = sum(item.unit_price * item.quantity for item in items)
    discount_factor = 1 - (discount_percent / 100.0)
    return round(subtotal * discount_factor, 2)


def low_stock(items: list[Item], threshold: int = 5) -> list[str]:
    """Names of items whose quantity is at or below the threshold."""
    return [item.name for item in items if item.quantity <= threshold]
