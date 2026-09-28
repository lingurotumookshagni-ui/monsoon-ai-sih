"""Deterministic meteorological heuristics used as a fallback.

The trained models are the primary path. These rules exist so that the API is
never broken: if `models/` is empty (fresh clone, before `train_models.py` has
been run) the endpoints still answer, clearly flagged with
``method = "heuristic_fallback"``.

The rules encode the same qualitative reasoning that shaped the synthetic data:
low pressure + very strong wind + saturated air -> depression; dry, hot, weak
flow -> break; high terrain with moist onshore flow -> orographic; cold, dry,
north-westerly in winter over the north -> western disturbance.
"""
from __future__ import annotations

from typing import Dict

import numpy as np


def diagnose_regime(f: Dict) -> Dict[str, float]:
    """Return a normalised score for each regime from raw features."""
    rh = float(f.get("humidity", 78))
    temp = float(f.get("temperature", 27))
    pres = float(f.get("pressure", 1002))
    ws = float(f.get("wind_speed", 6))
    lat = float(f.get("latitude", 18))
    elev = float(f.get("elevation", 300))
    coast = float(f.get("distance_from_coast", 200))
    month = int(f.get("month", 7))
    raw = float(f.get("raw_nwp_mm", 10))

    # Reduce station pressure to a rough sea-level equivalent so that highland
    # districts are not mistaken for deep lows.
    mslp = pres + 0.110 * elev
    coastal_prox = np.exp(-max(coast, 0) / 45.0)
    monsoon = month in (6, 7, 8, 9)
    winter = month in (11, 12, 1, 2, 3)

    s = {
        "MONSOON_DEPRESSION": max(0.0, (1000.0 - mslp) / 8.0) + max(0.0, (ws - 11) / 5.0)
                              + max(0.0, (rh - 88) / 10.0) + (0.4 if monsoon else 0.0)
                              + min(raw / 120.0, 1.0),
        "ACTIVE_MONSOON": max(0.0, (rh - 80) / 10.0) + max(0.0, (ws - 8) / 4.0)
                          + (0.9 if monsoon else 0.0) + min(raw / 90.0, 0.8),
        "BREAK_MONSOON": max(0.0, (72 - rh) / 10.0) + max(0.0, (temp - 31) / 3.0)
                         + max(0.0, (6 - ws) / 3.0) + (0.7 if monsoon else 0.0),
        "COASTAL_RAINFALL": 2.0 * coastal_prox + max(0.0, (rh - 80) / 12.0)
                            + (0.3 if monsoon else 0.1),
        "OROGRAPHIC_RAINFALL": min(elev / 700.0, 2.2) + max(0.0, (rh - 78) / 15.0),
        "WESTERN_DISTURBANCE": (1.6 if winter else 0.0) + max(0.0, (lat - 26) / 3.0)
                               + max(0.0, (18 - temp) / 6.0),
        "NORMAL_MONSOON": 0.9,
    }
    total = sum(s.values()) or 1.0
    return {k: v / total for k, v in s.items()}


# Fallback multiplicative correction factors applied to the raw NWP rainfall
# when no trained regime model is available. Derived from the systematic bias
# structure of the demo error model (see app/ml/synthetic.py).
FALLBACK_CORRECTION = {
    "ACTIVE_MONSOON": (1.14, -1.0),
    "BREAK_MONSOON": (0.80, -2.5),
    "MONSOON_DEPRESSION": (1.38, -1.0),
    "COASTAL_RAINFALL": (1.32, -1.5),
    "OROGRAPHIC_RAINFALL": (1.72, -1.0),
    "WESTERN_DISTURBANCE": (1.10, -1.5),
    "NORMAL_MONSOON": (1.04, -1.0),
}


def fallback_correction(raw_mm: float, regime: str, elevation: float = 0.0,
                        distance_from_coast: float = 200.0) -> float:
    """Heuristic bias correction; never returns a negative rainfall amount."""
    mult, add = FALLBACK_CORRECTION.get(regime, (1.0, 0.0))
    terrain = 1.0 + 0.12 * min(max(elevation, 0.0), 2500.0) / 2500.0
    coastal = 1.0 + 0.08 * float(np.exp(-max(distance_from_coast, 0.0) / 60.0))
    return float(max(0.0, raw_mm * mult * terrain * coastal + add))


def fallback_heavy_probability(rain_mm: float, threshold: float) -> float:
    """Smooth logistic probability that the true amount exceeds a threshold."""
    x = (float(rain_mm) - threshold) / max(threshold * 0.35, 1.0)
    return float(1.0 / (1.0 + np.exp(-x)))
