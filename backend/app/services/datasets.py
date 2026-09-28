"""Dataset access layer.

Everything the API serves comes through this module, which is the single seam
between MonsoonAI and its data. In DEMO MODE the data is synthetic (see
``app/ml/synthetic.py``). To go operational you replace the three loaders below
with readers for real sources - and nothing else in the codebase changes:

    load_districts()        -> district/grid metadata (shapefile, master list)
    load_forecast_cycle()   -> raw NWP rainfall forecast for the current cycle
    load_verification_set() -> matched forecast/observation archive

See the README section "Replacing demo data with real data".
"""
from __future__ import annotations

import datetime as dt
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from ..config import DEMO_MODE_BANNER, EVAL_CSV, LIVE_PROVIDER
from ..ml.registry import get_engine
from ..ml.synthetic import generate_forecast_snapshot, load_districts
from . import live_weather
from .live_weather import LiveDataError

_districts_cache: Optional[pd.DataFrame] = None
_forecast_cache: Dict[str, pd.DataFrame] = {}

# Processed live forecast cache, separate from live_weather's own per-point
# cache: this holds the *post-processed* DataFrame (after regime + correction
# + probability) so repeated dashboard calls in the same window don't re-run
# the model pipeline, only the raw provider fetch is cache-checked below it.
_live_cache: Dict[str, object] = {"frame": None, "expires_at": 0.0, "error": None}
LIVE_PROCESSED_CACHE_SECONDS = 120

# In-memory store for user-uploaded CSVs. Deliberately not a database: the
# prototype has no persistence requirement and no credentials to manage.
_uploaded: Dict[str, object] = {"frame": None, "meta": None}


# ------------------------------------------------------------- districts
def get_districts(refresh: bool = False) -> pd.DataFrame:
    global _districts_cache
    if _districts_cache is None or refresh:
        _districts_cache = load_districts()
    return _districts_cache.copy()


# --------------------------------------------------------- demo forecast
def load_forecast_cycle(for_date: Optional[dt.date] = None) -> pd.DataFrame:
    """Raw NWP-style forecast for one cycle, one row per district.

    DEMO MODE: synthesised deterministically from the date, so the dashboard is
    stable within a day. Replace with a reader for your NWP output
    (GRIB2/NetCDF -> district aggregation) to go live.
    """
    day = for_date or dt.date.today()
    snap = generate_forecast_snapshot(for_date=day, districts=get_districts())
    snap["forecast_date"] = day.isoformat()
    snap["data_source"] = "SYNTHETIC_DEMO"
    return snap


def get_forecast(for_date: Optional[dt.date] = None, refresh: bool = False) -> pd.DataFrame:
    """Processed district forecast product: regime + correction + probabilities."""
    day = (for_date or dt.date.today()).isoformat()
    if refresh or day not in _forecast_cache:
        raw = load_forecast_cycle(dt.date.fromisoformat(day))
        engine = get_engine()
        processed = engine.process(raw)
        # The synthetic "truth" used to build the demo forecast is dropped here:
        # a real forecast cycle has no observations yet, so serving it would be
        # misleading. Verification uses the archived hold-out set instead.
        processed = processed.drop(columns=["observed_rainfall_mm",
                                            "true_regime_synthetic"],
                                   errors="ignore")
        _forecast_cache.clear()
        _forecast_cache[day] = processed
    return _forecast_cache[day].copy()


def clear_forecast_cache() -> None:
    _forecast_cache.clear()


# ------------------------------------------------------------------- live
def get_live_forecast(refresh: bool = False) -> pd.DataFrame:
    """Live forecast, post-processed through the same trained pipeline as demo.

    Raises LiveDataError if the provider cannot be reached; callers (the
    /api/live/* and generic routes with source=live) must turn that into an
    explicit "unavailable" response rather than substituting synthetic rows.
    """
    import time as _time

    now = _time.time()
    if not refresh and _live_cache["frame"] is not None and _live_cache["expires_at"] > now:
        return _live_cache["frame"].copy()

    try:
        raw = live_weather.build_feature_frame(get_districts(), refresh=refresh)
        engine = get_engine()
        processed = engine.process(raw)
        processed["forecast_time"] = raw["forecast_time"].to_numpy()
        processed["fetched_at"] = raw["fetched_at"].to_numpy()
        processed["data_source"] = LIVE_PROVIDER
        _live_cache["frame"] = processed
        _live_cache["expires_at"] = now + LIVE_PROCESSED_CACHE_SECONDS
        _live_cache["error"] = None
        return processed.copy()
    except LiveDataError as exc:
        _live_cache["error"] = str(exc)
        raise


def live_status() -> Dict:
    """Reachability summary for GET /api/live/status, without a full fetch."""
    try:
        point = live_weather.ping()
        return {
            "mode": "LIVE",
            "source": LIVE_PROVIDER,
            "reachable": True,
            "last_success": live_weather.last_success(),
            "last_error": None,
            "sample_forecast_time": point.forecast_time,
            "sample_fetched_at": point.fetched_at,
        }
    except LiveDataError as exc:
        return {
            "mode": "UNAVAILABLE",
            "source": LIVE_PROVIDER,
            "reachable": False,
            "last_success": live_weather.last_success(),
            "last_error": str(exc),
            "sample_forecast_time": None,
            "sample_fetched_at": None,
        }


def clear_live_cache() -> None:
    _live_cache["frame"] = None
    _live_cache["expires_at"] = 0.0
    live_weather.clear_cache()


# ------------------------------------------------------------- uploaded data
def set_uploaded(frame: pd.DataFrame, meta: Dict) -> None:
    _uploaded["frame"] = frame
    _uploaded["meta"] = meta


def get_uploaded() -> Optional[pd.DataFrame]:
    frame = _uploaded.get("frame")
    return frame.copy() if isinstance(frame, pd.DataFrame) else None


def get_uploaded_meta() -> Optional[Dict]:
    return _uploaded.get("meta")  # type: ignore[return-value]


def clear_uploaded() -> None:
    _uploaded["frame"] = None
    _uploaded["meta"] = None


# --------------------------------------------------------- verification set
def load_verification_set() -> Optional[pd.DataFrame]:
    """Matched forecast/observation archive used by /api/verification.

    DEMO MODE: the temporal hold-out period written by ``train_models.py``
    (``outputs/eval_dataset.csv``). Replace with your own archive of
    (forecast, observation) pairs for real verification.
    """
    if not EVAL_CSV.exists():
        return None
    try:
        return pd.read_csv(EVAL_CSV)
    except Exception:
        return None


# ------------------------------------------------------------------ helpers
def forecast_records(df: pd.DataFrame) -> List[Dict]:
    """Serialise a processed forecast frame into JSON-friendly records."""
    cols = {
        "district": "district", "state": "state", "latitude": "lat",
        "longitude": "lon", "elevation": "elevation",
        "distance_from_coast": "distance_from_coast",
        "regime": "regime", "regime_confidence": "regime_confidence",
        "raw_nwp_mm": "raw_nwp_mm", "corrected_mm": "corrected_mm",
        "correction_mm": "correction_mm", "heavy_probability": "heavy_probability",
        "very_heavy_probability": "very_heavy_probability",
        "category": "category", "raw_category": "raw_category",
        "condition": "condition",
        "risk_band": "risk_band", "humidity": "humidity",
        "temperature": "temperature", "pressure": "pressure",
        "wind_speed": "wind_speed", "wind_direction": "wind_direction",
        "forecast_date": "forecast_date",
        "forecast_time": "forecast_time", "fetched_at": "fetched_at",
        "data_source": "data_source",
        "observed_rainfall_mm": "observed_rainfall_mm",
    }
    present = {src: dst for src, dst in cols.items() if src in df.columns}
    out = df[list(present.keys())].rename(columns=present)
    out = out.replace({np.nan: None})
    records = out.to_dict(orient="records")
    for r in records:
        for k, v in list(r.items()):
            if isinstance(v, (np.integer,)):
                r[k] = int(v)
            elif isinstance(v, (np.floating,)):
                r[k] = float(v)
    return records


def _banner_for(df: pd.DataFrame) -> str:
    source = df["data_source"].iloc[0] if "data_source" in df.columns and len(df) else None
    if source == LIVE_PROVIDER:
        return f"LIVE - {LIVE_PROVIDER}"
    if source == "SYNTHETIC_DEMO":
        return DEMO_MODE_BANNER
    if source == "USER_UPLOAD" or source is not None:
        return f"Uploaded data ({source})"
    return DEMO_MODE_BANNER


def summarise(df: pd.DataFrame) -> Dict:
    """KPI summary used by the Overview page."""
    if df.empty:
        return {"districts": 0, "heavy_alerts": 0, "very_heavy_alerts": 0,
                "active_regimes": 0, "mean_corrected_mm": 0.0,
                "mean_raw_mm": 0.0, "max_corrected_mm": 0.0,
                "demo_mode_banner": DEMO_MODE_BANNER}
    heavy = df["category"].isin(["HEAVY", "VERY_HEAVY", "EXTREMELY_HEAVY"]).sum()
    very = df["category"].isin(["VERY_HEAVY", "EXTREMELY_HEAVY"]).sum()
    return {
        "districts": int(len(df)),
        "states": int(df["state"].nunique()) if "state" in df.columns else 0,
        "heavy_alerts": int(heavy),
        "very_heavy_alerts": int(very),
        "active_regimes": int(df["regime"].nunique()),
        "mean_raw_mm": round(float(df["raw_nwp_mm"].mean()), 2),
        "mean_corrected_mm": round(float(df["corrected_mm"].mean()), 2),
        "mean_correction_mm": round(float(df["correction_mm"].mean()), 2),
        "max_corrected_mm": round(float(df["corrected_mm"].max()), 2),
        "top_district": str(df.loc[df["corrected_mm"].idxmax(), "district"]),
        "conditions": df["condition"].value_counts().to_dict() if "condition" in df.columns else {},
        "demo_mode_banner": _banner_for(df),
    }


def regime_summary(df: pd.DataFrame) -> List[Dict]:
    """Per-regime aggregation used by the Weather Regimes page."""
    if df.empty:
        return []
    grouped = df.groupby("regime")
    rows = []
    for regime, g in grouped:
        rows.append({
            "regime": str(regime),
            "districts": int(len(g)),
            "avg_raw_mm": round(float(g["raw_nwp_mm"].mean()), 2),
            "avg_corrected_mm": round(float(g["corrected_mm"].mean()), 2),
            "avg_correction_mm": round(float(g["correction_mm"].mean()), 2),
            "avg_confidence": round(float(g["regime_confidence"].mean()), 3),
            "avg_heavy_probability": round(float(g["heavy_probability"].mean()), 3),
            "heavy_alerts": int(g["category"].isin(
                ["HEAVY", "VERY_HEAVY", "EXTREMELY_HEAVY"]).sum()),
            "states": sorted(g["state"].unique().tolist()) if "state" in g.columns else [],
        })
    return sorted(rows, key=lambda r: -r["districts"])
