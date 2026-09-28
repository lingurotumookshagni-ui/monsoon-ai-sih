"""Root, health, district catalogue, regime catalogue and model-metrics routes."""
from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

from ..config import (
    DEMO_MODE_BANNER,
    LIVE_PROVIDER,
    RAINFALL_THRESHOLDS,
    REGIME_DESCRIPTIONS,
    REGIME_LABELS,
    REGIMES,
    RISK_BANDS,
    VERIFICATION_THRESHOLDS,
)
from ..ml.registry import get_engine
from ..ml.train import load_metrics
from ..schemas import HealthResponse
from ..services import datasets
from ..services.live_weather import LiveDataError

router = APIRouter()

VERSION = "1.0.0"

DISCLAIMER = (
    "This prototype is intended for research and hackathon demonstration. Demo "
    "forecasts are synthetic and are not official weather forecasts. Real "
    "operational deployment requires validated NWP forecasts, quality-controlled "
    "observations, appropriate regime definitions, spatial/temporal validation, "
    "calibration, and collaboration with meteorological experts."
)


@router.get("/", tags=["meta"])
def root() -> Dict[str, Any]:
    return {
        "name": "MonsoonAI",
        "subtitle": "Regime-Aware AI Post-Processing of Monsoon Rainfall Forecasts",
        "version": VERSION,
        "default_source": "live",
        "demo_mode": False,
        "banner": f"LIVE - forecasts fetched from {LIVE_PROVIDER}",
        "disclaimer": DISCLAIMER,
        "docs": "/docs",
        "endpoints": [
            "GET /api/health", "GET /api/forecast", "GET /api/overview",
            "GET /api/districts", "GET /api/districts/{name}", "POST /api/process",
            "GET /api/regimes", "POST /api/predict-regime",
            "GET /api/live/status", "GET /api/live/districts",
            "GET /api/live/rainfall/{district}", "POST /api/live/refresh",
            "POST /api/postprocess", "POST /api/heavy-rainfall-probability",
            "GET /api/verification", "POST /api/upload-data",
            "DELETE /api/upload-data", "GET /api/model-metrics",
        ],
    }


@router.get("/api/health", response_model=HealthResponse, tags=["meta"])
def health() -> Dict[str, Any]:
    """Backend and model status, plus a lightweight live-provider reachability
    check. This does NOT mean every district has live data cached - see
    GET /api/live/status and GET /api/live/rainfall/{district} for that."""
    engine = get_engine()
    try:
        n_districts = len(datasets.get_districts())
    except Exception:
        n_districts = 0

    live = datasets.live_status()

    return {
        "status": "ok",
        "default_source": "live",
        "demo_mode": False,
        "banner": (f"LIVE - {LIVE_PROVIDER}" if live["reachable"]
                  else "LIVE DATA UNAVAILABLE"),
        "models": engine.info(),
        "live": live,
        "districts_loaded": n_districts,
        "data_source": LIVE_PROVIDER if live["reachable"] else "UNAVAILABLE",
        "version": VERSION,
    }


@router.get("/api/districts", tags=["data"])
def districts() -> Dict[str, Any]:
    try:
        df = datasets.get_districts()
    except Exception:
        raise HTTPException(status_code=500, detail="District metadata could not be loaded.")
    return {
        "count": int(len(df)),
        "states": sorted(df["state"].unique().tolist()),
        "districts": df.to_dict(orient="records"),
        "note": "Geographic attributes are approximate values included for "
                "prototype demonstration.",
    }


@router.get("/api/regimes", tags=["data"])
def regimes(source: str = "live") -> Dict[str, Any]:
    """Regime catalogue plus per-regime statistics for the requested source's
    current cycle (default: live)."""
    catalogue: List[Dict[str, Any]] = [
        {
            "regime": r,
            "label": REGIME_LABELS[r],
            "description": REGIME_DESCRIPTIONS[r],
        }
        for r in REGIMES
    ]
    current: List[Dict[str, Any]] = []
    try:
        if source == "live":
            current = datasets.regime_summary(datasets.get_live_forecast())
        elif source == "uploaded":
            uploaded = datasets.get_uploaded()
            current = datasets.regime_summary(uploaded) if uploaded is not None else []
        else:
            current = datasets.regime_summary(datasets.get_forecast())
    except LiveDataError:
        current = []  # live unavailable: show the catalogue with zeroed stats,
                       # never demo numbers relabelled as live
    except Exception:
        current = []
    stats = {row["regime"]: row for row in current}
    for entry in catalogue:
        entry["current"] = stats.get(entry["regime"], {
            "districts": 0, "avg_raw_mm": 0.0, "avg_corrected_mm": 0.0,
            "avg_correction_mm": 0.0, "avg_confidence": 0.0,
            "avg_heavy_probability": 0.0, "heavy_alerts": 0, "states": [],
        })
    return {
        "regimes": catalogue,
        "note": "Regime classes are project-defined for this prototype and are not "
                "official meteorological regime classifications.",
    }


@router.get("/api/config", tags=["meta"])
def config() -> Dict[str, Any]:
    return {
        "rainfall_thresholds_mm": RAINFALL_THRESHOLDS,
        "verification_thresholds_mm": VERIFICATION_THRESHOLDS,
        "risk_bands": [{"band": b, "min_probability": p} for b, p in RISK_BANDS],
        "threshold_note": "Rainfall category thresholds are configurable. Exact "
                          "operational definitions should be verified against the "
                          "relevant official standard before operational deployment.",
        "risk_band_note": "Risk bands are prototype UI interpretation thresholds only.",
        "disclaimer": DISCLAIMER,
    }


@router.get("/api/model-metrics", tags=["meta"])
def model_metrics() -> Dict[str, Any]:
    metrics = load_metrics()
    if metrics is None:
        raise HTTPException(
            status_code=404,
            detail="No training metrics found. Run 'python train_models.py' first.",
        )
    return metrics
