"""Live-mode API routes.

These wrap the same district catalogue and the same trained-model pipeline
used everywhere else in the project (`app/services/datasets.py`,
`app/ml/registry.py`); the only new code is `app/services/live_weather.py`,
which turns an Open-Meteo forecast into the model's feature format. Nothing
here bypasses the regime classifier or the correction models.
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query

from ..config import LIVE_CACHE_TTL_SECONDS, LIVE_PROVIDER, LIVE_WINDOW_HOURS
from ..services import datasets
from ..services.live_weather import LiveDataError

router = APIRouter(prefix="/api/live", tags=["live"])


@router.get("/status")
def status() -> Dict[str, Any]:
    """Reachability of the live provider, without fetching every district.

    Pings a single fixed coordinate. Used by the frontend's LIVE / OFFLINE
    indicator; it does not imply every district has fresh data cached.
    """
    result = datasets.live_status()
    result["window_hours"] = LIVE_WINDOW_HOURS
    result["cache_ttl_seconds"] = LIVE_CACHE_TTL_SECONDS
    return result


@router.get("/districts")
def live_districts() -> Dict[str, Any]:
    """The full district catalogue available in live mode - every district,
    not only ones with heavy rainfall."""
    df = datasets.get_districts()
    return {
        "count": int(len(df)),
        "states": sorted(df["state"].unique().tolist()),
        "districts": df.to_dict(orient="records"),
        "note": "All districts support live lookup. Heavy rainfall alerts are a "
                "separate, additional view - not a filter on this list.",
    }


@router.get("/rainfall/{district_name}")
def live_rainfall(district_name: str, refresh: bool = Query(False)) -> Dict[str, Any]:
    """Live forecast, regime and AI-corrected rainfall for one district.

    Example response shape:
        {"mode": "LIVE", "district": "Kozhikode", "source": "Open-Meteo",
         "forecast_time": "...", "last_updated": "...", "raw_rainfall_mm": 0,
         "post_processed_rainfall_mm": 0, "rainfall_probability": 0,
         "regime": "...", "category": "...", "model_used": "..."}
    """
    try:
        df = datasets.get_live_forecast(refresh=refresh)
    except LiveDataError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    match = df[df["district"].str.lower() == district_name.strip().lower()]
    if match.empty:
        match = df[df["district"].str.lower().str.contains(district_name.strip().lower())]
    if match.empty:
        raise HTTPException(
            status_code=404,
            detail=f"No district named '{district_name}' in the district catalogue.",
        )

    row = match.iloc[0]
    return {
        "mode": "LIVE",
        "district": row["district"],
        "state": row.get("state"),
        "source": LIVE_PROVIDER,
        "forecast_time": row.get("forecast_time"),
        "last_updated": row.get("fetched_at"),
        "window_hours": LIVE_WINDOW_HOURS,
        "raw_rainfall_mm": float(row["raw_nwp_mm"]),
        "post_processed_rainfall_mm": float(row["corrected_mm"]),
        "correction_mm": float(row["correction_mm"]),
        "rainfall_probability": float(row["heavy_probability"]),
        "very_heavy_probability": float(row["very_heavy_probability"]),
        "regime": row["regime"],
        "regime_confidence": float(row["regime_confidence"]),
        "category": row["category"],
        "condition": row.get("condition"),
        "model_used": row.get("correction_method"),
        "observed_rainfall_mm": None,
        "note": "observed_rainfall_mm is null because the forecast window has not "
                "occurred yet - this is a forecast, not a verified observation.",
    }


@router.post("/refresh")
def live_refresh() -> Dict[str, Any]:
    """Force a fresh fetch from the provider for every district, bypassing the cache."""
    datasets.clear_live_cache()
    try:
        df = datasets.get_live_forecast(refresh=True)
    except LiveDataError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return {
        "status": "refreshed",
        "source": LIVE_PROVIDER,
        "districts": int(len(df)),
        "fetched_at": str(df["fetched_at"].iloc[0]) if len(df) else None,
    }
