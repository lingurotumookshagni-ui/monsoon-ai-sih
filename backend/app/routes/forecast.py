"""District-level forecast product routes."""
from __future__ import annotations

import datetime as dt
import time
from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from ..config import (
    DEMO_MODE_BANNER,
    LIVE_PROVIDER,
    RAINFALL_THRESHOLDS,
    REGIME_DESCRIPTIONS,
    REGIME_LABELS,
)
from ..ml.registry import get_engine
from ..services import datasets, verification
from ..services.live_weather import LiveDataError

router = APIRouter(prefix="/api", tags=["forecast"])


def _resolve_frame(source: str, for_date: Optional[str], refresh: bool = False) -> pd.DataFrame:
    """Pick the active dataset: live, the synthetic demo cycle, or an uploaded CSV."""
    if source == "live":
        try:
            return datasets.get_live_forecast(refresh=refresh)
        except LiveDataError as exc:
            # 503 Service Unavailable, not 200 with fabricated rows: the
            # frontend must show "LIVE DATA UNAVAILABLE", never silently
            # substitute demo data for a failed live request.
            raise HTTPException(status_code=503, detail=str(exc))
    if source == "uploaded":
        frame = datasets.get_uploaded()
        if frame is None or frame.empty:
            raise HTTPException(
                status_code=404,
                detail="No uploaded dataset in this session. Upload a CSV at "
                       "POST /api/upload-data or use source=demo.",
            )
        return frame
    day = None
    if for_date:
        try:
            day = dt.date.fromisoformat(for_date)
        except ValueError:
            raise HTTPException(status_code=422,
                                detail="Invalid 'date'. Use YYYY-MM-DD.")
    return datasets.get_forecast(for_date=day)


def _apply_filters(df: pd.DataFrame, state, district, regime, category,
                   min_heavy_probability, min_rainfall) -> pd.DataFrame:
    out = df
    if state:
        out = out[out["state"].str.lower() == state.strip().lower()]
    if district:
        out = out[out["district"].str.lower().str.contains(district.strip().lower())]
    if regime:
        out = out[out["regime"].str.upper() == regime.strip().upper()]
    if category:
        out = out[out["category"].str.upper() == category.strip().upper()]
    if min_heavy_probability is not None:
        out = out[out["heavy_probability"] >= float(min_heavy_probability)]
    if min_rainfall is not None:
        out = out[out["corrected_mm"] >= float(min_rainfall)]
    return out


@router.get("/forecast")
def forecast(
    state: Optional[str] = Query(None, description="Filter by state name"),
    district: Optional[str] = Query(None, description="Filter by district (substring match)"),
    regime: Optional[str] = Query(None, description="Filter by weather regime"),
    category: Optional[str] = Query(None, description="Filter by rainfall category"),
    min_heavy_probability: Optional[float] = Query(None, ge=0, le=1),
    min_rainfall: Optional[float] = Query(None, ge=0),
    sort_by: str = Query("corrected_mm", description="corrected_mm | raw_nwp_mm | heavy_probability | district"),
    limit: int = Query(500, ge=1, le=5000),
    source: str = Query("live", pattern="^(demo|uploaded|live)$"),
    date: Optional[str] = Query(None, description="Forecast date (YYYY-MM-DD), demo source only"),
) -> List[Dict[str, Any]]:
    """District forecasts: raw NWP, regime, AI-corrected rainfall, probabilities."""
    df = _resolve_frame(source, date)
    df = _apply_filters(df, state, district, regime, category,
                        min_heavy_probability, min_rainfall)
    if sort_by in df.columns:
        ascending = sort_by == "district"
        df = df.sort_values(sort_by, ascending=ascending)
    return datasets.forecast_records(df.head(limit))


@router.get("/forecast/summary")
def forecast_summary(
    source: str = Query("live", pattern="^(demo|uploaded|live)$"),
    date: Optional[str] = None,
) -> Dict[str, Any]:
    df = _resolve_frame(source, date)
    return {
        "source": source,
        "kpis": datasets.summarise(df),
        "regimes": datasets.regime_summary(df),
        "categories": df["category"].value_counts().to_dict(),
    }


@router.get("/overview")
def overview(
    source: str = Query("live", pattern="^(demo|uploaded|live)$"),
    date: Optional[str] = None,
) -> Dict[str, Any]:
    """Everything the Overview page needs in a single request."""
    df = _resolve_frame(source, date)
    kpis = datasets.summarise(df)

    # Headline verification numbers only apply to the demo hold-out period:
    # live forecasts describe a window that has not happened yet, so there is
    # nothing to verify them against, and an uploaded CSV is only verifiable
    # when it carries its own observed_rainfall_mm column.
    ver_summary: Dict[str, Any] = {"available": False}
    if source == "demo":
        eval_df = datasets.load_verification_set()
        if eval_df is not None and {"raw_nwp_mm", "corrected_mm",
                                    "observed_rainfall_mm"}.issubset(eval_df.columns):
            report = verification.compare(eval_df)
            ver_summary = {
                "available": True,
                "raw_rmse": report["raw_nwp"]["rmse"],
                "ai_rmse": report["ai_corrected"]["rmse"],
                "raw_mae": report["raw_nwp"]["mae"],
                "ai_mae": report["ai_corrected"]["mae"],
                "rmse_reduction_pct": report["improvement"]["rmse_reduction_pct"],
                "sample_size": report["sample_size"],
            }
    elif source == "uploaded" and "observed_rainfall_mm" in df.columns and df["observed_rainfall_mm"].notna().any():
        subset = df.dropna(subset=["observed_rainfall_mm"])
        report = verification.compare(subset)
        ver_summary = {
            "available": True,
            "raw_rmse": report["raw_nwp"]["rmse"],
            "ai_rmse": report["ai_corrected"]["rmse"],
            "raw_mae": report["raw_nwp"]["mae"],
            "ai_mae": report["ai_corrected"]["mae"],
            "rmse_reduction_pct": report["improvement"]["rmse_reduction_pct"],
            "sample_size": report["sample_size"],
        }
    elif source == "live":
        ver_summary = {
            "available": False,
            "reason": "Live forecasts have no observed rainfall yet.",
        }

    top = df.sort_values("corrected_mm", ascending=False).head(10)
    return {
        "banner": kpis.get("demo_mode_banner", DEMO_MODE_BANNER),
        "source": source,
        "forecast_date": str(df["forecast_date"].iloc[0]) if "forecast_date" in df.columns and len(df) else None,
        "kpis": kpis,
        "verification": ver_summary,
        "regimes": datasets.regime_summary(df),
        "categories": df["category"].value_counts().to_dict(),
        "top_districts": datasets.forecast_records(top),
        "map_points": datasets.forecast_records(df),
    }


@router.get("/heavy-rainfall")
def heavy_rainfall(
    min_probability: float = Query(0.0, ge=0, le=1),
    source: str = Query("live", pattern="^(demo|uploaded|live)$"),
    date: Optional[str] = None,
    limit: int = Query(500, ge=1, le=5000),
) -> Dict[str, Any]:
    """Ranked heavy-rainfall watchlist for the Heavy Rainfall page."""
    df = _resolve_frame(source, date)
    df = df[df["heavy_probability"] >= min_probability]
    df = df.sort_values("heavy_probability", ascending=False).head(limit)
    bands = df["risk_band"].value_counts().to_dict() if "risk_band" in df.columns else {}
    return {
        "source": source,
        "count": int(len(df)),
        "risk_bands": bands,
        "districts": datasets.forecast_records(df),
        "note": "Risk bands are prototype UI interpretation thresholds applied to "
                "model probabilities, not official warning criteria.",
    }


@router.get("/districts/{district_name}")
def district_detail(
    district_name: str,
    source: str = Query("live", pattern="^(demo|uploaded|live)$"),
    date: Optional[str] = None,
) -> Dict[str, Any]:
    """Everything known about one district: the citizen view and the technical view.

    Powers the "Check your district" lookup and the district detail panel. The
    explanation is returned as a *key* (not a sentence) so the dashboard can
    render it in the user's selected language without the backend guessing.
    """
    df = _resolve_frame(source, date)
    match = df[df["district"].str.lower() == district_name.strip().lower()]
    if match.empty:
        match = df[df["district"].str.lower().str.contains(district_name.strip().lower())]
    if match.empty:
        raise HTTPException(
            status_code=404,
            detail=f"No district named '{district_name}' in the active dataset.",
        )

    record = datasets.forecast_records(match.head(1))[0]
    regime = str(record.get("regime", "NORMAL_MONSOON"))
    data_source = {"live": LIVE_PROVIDER, "uploaded": "USER_UPLOAD"}.get(source, "SYNTHETIC_DEMO")

    return {
        "source": source,
        "district": record,
        "explanation_key": f"explanation.{record.get('condition', 'NORMAL')}",
        "regime": {
            "code": regime,
            "label": REGIME_LABELS.get(regime, regime),
            "description": REGIME_DESCRIPTIONS.get(regime, ""),
            "confidence": record.get("regime_confidence"),
        },
        "thresholds_mm": {
            "heavy": RAINFALL_THRESHOLDS["HEAVY_MIN"],
            "very_heavy": RAINFALL_THRESHOLDS["VERY_HEAVY_MIN"],
        },
        "data_source": data_source,
        "demo_mode": source == "demo",
    }


@router.post("/process")
def process_cycle(
    source: str = Query("live", pattern="^(demo|uploaded|live)$"),
    date: Optional[str] = None,
) -> Dict[str, Any]:
    """Run the full pipeline now and report what each stage actually did.

    The dashboard's processing view reads these stages, so the progress it
    shows reflects real backend work (row counts, timings, models used) rather
    than a scripted animation.
    """
    stages: List[Dict[str, Any]] = []

    def stage(key: str, label: str, fn):
        started = time.perf_counter()
        try:
            detail = fn()
            status = "done"
        except HTTPException:
            raise
        except Exception:
            detail = {}
            status = "failed"
        stages.append({
            "key": key,
            "label": label,
            "status": status,
            "ms": round((time.perf_counter() - started) * 1000, 1),
            "detail": detail,
        })
        return detail

    engine = get_engine()
    datasets.clear_forecast_cache()

    raw_holder: Dict[str, Any] = {}

    def load():
        if source == "uploaded":
            frame = datasets.get_uploaded()
            if frame is None or frame.empty:
                raise HTTPException(status_code=404, detail="No uploaded dataset in this session.")
        elif source == "live":
            try:
                frame = datasets.get_live_forecast(refresh=True)
            except LiveDataError as exc:
                raise HTTPException(status_code=503, detail=str(exc))
        else:
            day = dt.date.fromisoformat(date) if date else None
            frame = datasets.load_forecast_cycle(day)
        raw_holder["frame"] = frame
        return {"rows": int(len(frame)), "districts": int(frame["district"].nunique())}

    stage("load", "Loading rainfall data", load)
    frame = raw_holder["frame"]

    regimes = stage(
        "regime", "Detecting weather regime",
        lambda: {
            "method": engine.info()["mode"],
            "counts": engine.predict_regime(frame)["regime"].value_counts().to_dict(),
        },
    )

    if source == "demo":
        processed = datasets.get_forecast(
            for_date=dt.date.fromisoformat(date) if date else None
        )
    elif source == "live":
        processed = frame  # already fully processed by get_live_forecast()
    else:
        processed = datasets.get_uploaded()

    stage("postprocess", "Applying AI post-processing", lambda: {
        "mean_correction_mm": round(float(processed["correction_mm"].mean()), 2),
        "models_used": sorted(set(processed["correction_method"].tolist()))
        if "correction_method" in processed.columns else [],
    })
    stage("probability", "Calculating rainfall probabilities", lambda: {
        "mean_heavy_probability": round(float(processed["heavy_probability"].mean()), 3),
        "districts_above_50pct": int((processed["heavy_probability"] >= 0.5).sum()),
    })

    def metrics():
        eval_df = datasets.load_verification_set()
        if eval_df is None:
            return {"available": False}
        report = verification.compare(eval_df)
        return {
            "available": True,
            "raw_rmse": report["raw_nwp"]["rmse"],
            "ai_rmse": report["ai_corrected"]["rmse"],
            "sample_size": report["sample_size"],
        }

    stage("metrics", "Calculating evaluation metrics", metrics)
    stage("results", "Generating district results", lambda: datasets.summarise(processed))
    stage("visualisation", "Preparing visualisation", lambda: {
        "map_points": int(len(processed)),
        "conditions": processed["condition"].value_counts().to_dict()
        if "condition" in processed.columns else {},
    })

    return {
        "status": "complete",
        "source": source,
        "demo_mode": source != "uploaded",
        "engine_mode": engine.info()["mode"],
        "total_ms": round(sum(s["ms"] for s in stages), 1),
        "stages": stages,
    }
