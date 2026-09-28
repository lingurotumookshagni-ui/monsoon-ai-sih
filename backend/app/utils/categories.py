"""Rainfall category / risk-band helpers.

All thresholds come from app.config so they stay configurable.
"""
from __future__ import annotations

from ..config import PUBLIC_CONDITIONS
from ..config import RAINFALL_THRESHOLDS as T
from ..config import RISK_BANDS


def rainfall_category(mm: float) -> str:
    """Map a 24 h rainfall accumulation (mm) to a prototype category."""
    if mm is None:
        return "UNKNOWN"
    mm = float(mm)
    if mm < T["LIGHT_MAX"]:
        return "LIGHT"
    if mm <= T["MODERATE_MAX"]:
        return "MODERATE"
    if mm <= T["HEAVY_MAX"]:
        return "HEAVY"
    if mm <= T["VERY_HEAVY_MAX"]:
        return "VERY_HEAVY"
    return "EXTREMELY_HEAVY"


def risk_band(probability: float) -> str:
    """Prototype UI interpretation of a heavy-rainfall probability."""
    p = float(probability or 0.0)
    for name, floor in RISK_BANDS:
        if p >= floor:
            return name
    return "LOW"


def category_order(category: str) -> int:
    """Sortable severity rank for a rainfall category."""
    order = ["LIGHT", "MODERATE", "HEAVY", "VERY_HEAVY", "EXTREMELY_HEAVY"]
    return order.index(category) if category in order else -1


def public_condition(mm: float) -> str:
    """Plain-language condition band for the citizen-facing district lookup.

    Derived from the same configured rainfall thresholds as `rainfall_category`
    (see PUBLIC_CONDITIONS in app/config.py); it does not introduce any new
    scientific threshold, it only makes the low end readable for non-specialists.
    """
    if mm is None:
        return "UNKNOWN"
    value = float(mm)
    for name, floor in PUBLIC_CONDITIONS:
        if value >= floor:
            return name
    return "LOW"


def condition_order(condition: str) -> int:
    order = ["LOW", "NORMAL", "MODERATE", "HEAVY", "VERY_HEAVY"]
    return order.index(condition) if condition in order else -1
