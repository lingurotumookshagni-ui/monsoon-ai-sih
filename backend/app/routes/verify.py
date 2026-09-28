"""Verification route: raw NWP vs AI-corrected vs observed."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from ..config import VERIFICATION_THRESHOLDS
from ..services import datasets, verification

router = APIRouter(prefix="/api", tags=["verification"])


@router.get("/verification")
def get_verification(
    source: str = Query("live", pattern="^(demo|uploaded|live)$"),
    thresholds: Optional[str] = Query(
        None, description="Comma-separated mm thresholds, e.g. 64.5,115.6,204.5"),
    fss_radius_km: float = Query(150.0, ge=10, le=1000),
) -> Dict[str, Any]:
    """Verification report comparing the raw NWP and the AI-corrected forecast.

    ``source=demo`` uses the temporal hold-out period produced by
    ``train_models.py``; ``source=uploaded`` verifies an uploaded CSV that
    contains an ``observed_rainfall_mm`` column.
    """
    thr: List[float] = VERIFICATION_THRESHOLDS
    if thresholds:
        try:
            thr = [float(t) for t in thresholds.split(",") if t.strip()]
        except ValueError:
            raise HTTPException(status_code=422,
                                detail="'thresholds' must be comma-separated numbers.")
        if not thr:
            raise HTTPException(status_code=422, detail="No valid thresholds supplied.")

    if source == "live":
        # A live forecast has no observed rainfall yet - the 24 h window it
        # describes has not happened. Computing RMSE/CSI/POD/FAR/FSS against
        # anything else (e.g. the demo hold-out set) would misrepresent live
        # forecast skill, so this is reported as unavailable rather than
        # silently substituting a different dataset's numbers.
        return {
            "available": False,
            "source": "live",
            "reason": "Live forecasts have no matching observed rainfall yet, so "
                      "verification scores cannot be computed for them. Scores "
                      "shown elsewhere for 'demo' come from a held-out synthetic "
                      "period the models were evaluated against during training.",
            "thresholds_mm": thr,
        }
    if source == "uploaded":
        df = datasets.get_uploaded()
        if df is None or df.empty:
            raise HTTPException(status_code=404,
                                detail="No uploaded dataset in this session.")
        if "observed_rainfall_mm" not in df.columns or df["observed_rainfall_mm"].isna().all():
            raise HTTPException(
                status_code=422,
                detail="The uploaded dataset has no 'observed_rainfall_mm' values, "
                       "so it cannot be verified.")
        df = df.dropna(subset=["observed_rainfall_mm"])
        dataset_label = "USER_UPLOAD"
    else:
        df = datasets.load_verification_set()
        if df is None or df.empty:
            raise HTTPException(
                status_code=404,
                detail="No evaluation dataset found. Run 'python train_models.py' "
                       "to generate outputs/eval_dataset.csv.")
        dataset_label = "SYNTHETIC_DEMO_HOLDOUT"

    missing = {"raw_nwp_mm", "corrected_mm", "observed_rainfall_mm"} - set(df.columns)
    if missing:
        raise HTTPException(status_code=422,
                            detail=f"Dataset is missing columns: {sorted(missing)}")

    report = verification.compare(df, thresholds=thr)
    report["source"] = source
    report["dataset"] = dataset_label
    report["fss_radius_km"] = fss_radius_km
    if "date" in df.columns:
        report["period"] = {"start": str(df["date"].min()), "end": str(df["date"].max())}
    report["districts"] = int(df["district"].nunique()) if "district" in df.columns else None
    return report
