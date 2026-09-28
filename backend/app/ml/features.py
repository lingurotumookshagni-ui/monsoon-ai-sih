"""Feature engineering shared by the training pipeline and the live API.

Keeping one single implementation here is what guarantees that the model sees
exactly the same columns, in the same order, at training time and at
prediction time. Adding a feature means editing this file only.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..config import REGIMES

# Raw meteorological / geographic inputs the system expects.
RAW_INPUT_COLUMNS = [
    "raw_nwp_mm",
    "humidity",
    "temperature",
    "pressure",
    "wind_speed",
    "wind_direction",
    "latitude",
    "longitude",
    "elevation",
    "distance_from_coast",
    "month",
    "day_of_year",
]

# Sensible fallbacks so a partially-filled request never crashes the API.
# (Monsoon-season medians over the demo district set.)
DEFAULTS = {
    "raw_nwp_mm": 10.0,
    "humidity": 78.0,
    "temperature": 27.0,
    "pressure": 1002.0,
    "wind_speed": 6.0,
    "wind_direction": 225.0,
    "latitude": 18.0,
    "longitude": 78.0,
    "elevation": 300.0,
    "distance_from_coast": 200.0,
    "month": 7,
    "day_of_year": 196,
}

# Engineered feature vector used by the regime classifier.
REGIME_FEATURES = [
    "raw_nwp_mm",
    "log_raw_nwp",
    "humidity",
    "temperature",
    "pressure",
    "wind_speed",
    "wind_dir_sin",
    "wind_dir_cos",
    "latitude",
    "longitude",
    "elevation",
    "log_elevation",
    "distance_from_coast",
    "coastal_proximity",
    "month",
    "doy_sin",
    "doy_cos",
]

# Correction / heavy-rain models additionally know which regime they are in
# (per-regime models see a constant column, which tree models simply ignore).
RAINFALL_FEATURES = REGIME_FEATURES + ["regime_code"]

REGIME_CODES = {name: i for i, name in enumerate(REGIMES)}
CODE_TO_REGIME = {i: name for name, i in REGIME_CODES.items()}


def regime_code(regime: str) -> int:
    return REGIME_CODES.get(str(regime).upper(), REGIME_CODES["NORMAL_MONSOON"])


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of ``df`` with every engineered feature column present.

    Missing optional columns are filled with the defaults above; the derived
    columns (cyclical time, wind direction components, log transforms) are
    always recomputed so training and inference cannot drift apart.
    """
    out = df.copy()

    for col, default in DEFAULTS.items():
        if col not in out.columns:
            out[col] = default
        else:
            out[col] = pd.to_numeric(out[col], errors="coerce").fillna(default)

    # Rainfall is strongly right-skewed: a log transform gives tree models a
    # better-behaved split space for the light-rain part of the distribution.
    out["log_raw_nwp"] = np.log1p(out["raw_nwp_mm"].clip(lower=0))
    out["log_elevation"] = np.log1p(out["elevation"].clip(lower=0))

    # Coastal proximity decays with an e-folding distance of ~60 km, which is
    # roughly the width of the onshore-flow rainfall belt in the demo data.
    out["coastal_proximity"] = np.exp(-out["distance_from_coast"].clip(lower=0) / 60.0)

    # Wind direction is circular -> encode as sine/cosine instead of degrees.
    rad = np.deg2rad(out["wind_direction"])
    out["wind_dir_sin"] = np.sin(rad)
    out["wind_dir_cos"] = np.cos(rad)

    # Seasonality is circular too.
    doy_rad = 2 * np.pi * out["day_of_year"] / 365.25
    out["doy_sin"] = np.sin(doy_rad)
    out["doy_cos"] = np.cos(doy_rad)

    if "regime" in out.columns:
        out["regime_code"] = out["regime"].map(regime_code).astype(int)
    elif "regime_code" not in out.columns:
        out["regime_code"] = REGIME_CODES["NORMAL_MONSOON"]

    return out


def regime_matrix(df: pd.DataFrame) -> pd.DataFrame:
    return build_features(df)[REGIME_FEATURES]


def rainfall_matrix(df: pd.DataFrame) -> pd.DataFrame:
    return build_features(df)[RAINFALL_FEATURES]
