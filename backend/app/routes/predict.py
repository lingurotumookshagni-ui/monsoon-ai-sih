"""Single-point inference routes: regime, post-processing, heavy-rain probability."""
from __future__ import annotations

from typing import Any, Dict

import pandas as pd
from fastapi import APIRouter, HTTPException

from ..config import RAINFALL_THRESHOLDS
from ..ml.registry import get_engine
from ..schemas import (
    HeavyRainfallResponse,
    PostProcessResponse,
    RegimeResponse,
    WeatherFeatures,
)
from ..utils.categories import rainfall_category, risk_band

router = APIRouter(prefix="/api", tags=["inference"])

REGIME_DISCLAIMER = (
    "Regime classes are project-defined for this prototype and trained on "
    "synthetic data; they are not official meteorological regime classifications."
)


def _frame(payload: WeatherFeatures) -> pd.DataFrame:
    return pd.DataFrame([payload.to_row()])


@router.post("/predict-regime", response_model=RegimeResponse)
def predict_regime(payload: WeatherFeatures) -> Dict[str, Any]:
    """Classify the prevailing weather regime from meteorological features."""
    try:
        result = get_engine().predict_regime(_frame(payload)).iloc[0]
    except Exception:
        raise HTTPException(status_code=500, detail="Regime classification failed.")
    return {
        "regime": str(result["regime"]),
        "confidence": float(result["regime_confidence"]),
        "probabilities": dict(result["regime_probabilities"]),
        "method": str(result["regime_method"]),
        "disclaimer": REGIME_DISCLAIMER,
    }


@router.post("/postprocess", response_model=PostProcessResponse)
def postprocess(payload: WeatherFeatures) -> Dict[str, Any]:
    """Regime-aware bias correction of a single raw NWP rainfall forecast."""
    try:
        row = get_engine().process(
            _frame(payload), use_given_regime=bool(payload.regime)
        ).iloc[0]
    except Exception:
        raise HTTPException(status_code=500, detail="Post-processing failed.")
    return {
        "district": payload.district,
        "state": payload.state,
        "regime": str(row["regime"]),
        "regime_confidence": float(row["regime_confidence"]),
        "raw_nwp_mm": float(row["raw_nwp_mm"]),
        "corrected_rainfall_mm": float(row["corrected_mm"]),
        "correction_mm": float(row["correction_mm"]),
        "confidence": float(row["regime_confidence"]),
        "category": str(row["category"]),
        "heavy_probability": float(row["heavy_probability"]),
        "very_heavy_probability": float(row["very_heavy_probability"]),
        "method": str(row["correction_method"]),
        "data_source": "SYNTHETIC_DEMO",
    }


@router.post("/heavy-rainfall-probability", response_model=HeavyRainfallResponse)
def heavy_rainfall_probability(payload: WeatherFeatures) -> Dict[str, Any]:
    """Probability that the true 24 h rainfall reaches heavy / very heavy levels."""
    try:
        row = get_engine().process(
            _frame(payload), use_given_regime=bool(payload.regime)
        ).iloc[0]
    except Exception:
        raise HTTPException(status_code=500, detail="Probability estimation failed.")
    expected = float(row["corrected_mm"])
    return {
        "probability_heavy": float(row["heavy_probability"]),
        "probability_very_heavy": float(row["very_heavy_probability"]),
        "category": rainfall_category(expected),
        "risk_band": risk_band(float(row["heavy_probability"])),
        "expected_rainfall_mm": expected,
        "raw_nwp_mm": float(row["raw_nwp_mm"]),
        "regime": str(row["regime"]),
        "thresholds_mm": {
            "heavy": RAINFALL_THRESHOLDS["HEAVY_MIN"],
            "very_heavy": RAINFALL_THRESHOLDS["VERY_HEAVY_MIN"],
            "extremely_heavy": RAINFALL_THRESHOLDS["EXTREMELY_HEAVY_MIN"],
        },
        "method": str(row["heavy_probability_method"]),
    }
