"""A tiny units module for Steward's held-out evals: lengths converted, temperatures converted, quantities formatted."""

# How many metres one of each length unit is.
LENGTH_IN_METRES = {"mm": 0.001, "cm": 0.01, "m": 1.0, "km": 1000.0, "in": 0.0254, "ft": 0.3048}


def convert_length(value: float, from_unit: str, to_unit: str) -> float:
    """A length in one unit given in another, both named in LENGTH_IN_METRES."""
    if from_unit not in LENGTH_IN_METRES or to_unit not in LENGTH_IN_METRES:
        raise ValueError(f"unknown length unit: {from_unit if from_unit not in LENGTH_IN_METRES else to_unit}")
    return value * LENGTH_IN_METRES[from_unit] / LENGTH_IN_METRES[to_unit]


def celsius_to_fahrenheit(celsius: float) -> float:
    """Degrees Celsius in degrees Fahrenheit."""
    return celsius * 9 / 5 + 32


def format_quantity(value: float, unit: str, places: int = 2) -> str:
    """A value and its unit as text, e.g. format_quantity(1.5, "km") is "1.50 km"."""
    return f"{value:.{places}f} {unit}"
