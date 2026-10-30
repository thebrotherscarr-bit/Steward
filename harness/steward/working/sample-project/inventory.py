"""A tiny inventory module for Steward to work on. It has a bug that test_inventory.py catches."""

from dataclasses import dataclass


@dataclass
class Item:
    name: str
    unit_price: float
    quantity: int


def order_total(items: list[Item], discount_percent: float = 0.0) -> float:
    """Total price of an order after a percentage discount, rounded to cents."""
    subtotal = sum(item.unit_price * item.quantity for item in items)
    return round(subtotal * (1 - discount_percent / 100), 2)

def low_stock(items: list[Item], threshold: int = 5) -> list[str]:
    """Names of items whose quantity is at or below the threshold."""
    return [item.name for item in items if item.quantity <= threshold]
