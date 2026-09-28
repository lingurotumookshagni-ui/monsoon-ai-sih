"""Forecast verification module.

Implements the standard verification scores used to decide whether the
regime-aware post-processing actually adds skill over the raw NWP forecast:

Continuous:   RMSE, MAE, mean bias, correlation
Categorical:  POD, FAR, CSI, ETS (at configurable rainfall thresholds)
Spatial:      FSS (neighbourhood Fractions Skill Score - simplified,
              station/district based rather than gridded; see note below)

Every score guards against division by zero and returns ``None`` when the
score is genuinely undefined (e.g. POD with no observed events), so the API
never raises and the dashboard can show "n/a" honestly.
"""
from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from ..config import VERIFICATION_THRESHOLDS

EARTH_RADIUS_KM = 6371.0


# ---------------------------------------------------------------- helpers
def _safe_div(num: float, den: float) -> Optional[float]:
    """Divide, returning None instead of raising/NaN when the denominator is 0."""
    if den is None or den == 0:
        return None
    return float(num) / float(den)


def _round(value: Optional[float], nd: int = 4) -> Optional[float]:
    if value is None or (isinstance(value, float) and not np.isfinite(value)):
        return None
    return round(float(value), nd)


# ------------------------------------------------------------- continuous
def continuous_scores(forecast: np.ndarray, observed: np.ndarray) -> Dict[str, Optional[float]]:
    f = np.asarray(forecast, dtype=float)
    o = np.asarray(observed, dtype=float)
    mask = np.isfinite(f) & np.isfinite(o)
    f, o = f[mask], o[mask]
    if f.size == 0:
        return {"rmse": None, "mae": None, "bias": None, "correlation": None, "n": 0}

    err = f - o
    corr = None
    if f.size > 2 and f.std() > 1e-9 and o.std() > 1e-9:
        corr = float(np.corrcoef(f, o)[0, 1])
    return {
        "rmse": _round(np.sqrt(np.mean(err ** 2)), 3),
        "mae": _round(np.mean(np.abs(err)), 3),
        "bias": _round(np.mean(err), 3),
        "correlation": _round(corr, 3),
        "n": int(f.size),
    }


# ------------------------------------------------------------ categorical
def contingency_table(forecast: np.ndarray, observed: np.ndarray, threshold: float) -> Dict[str, int]:
    """2x2 contingency table for 'rainfall >= threshold' events."""
    f = np.asarray(forecast, dtype=float) >= threshold
    o = np.asarray(observed, dtype=float) >= threshold
    return {
        "hits": int(np.sum(f & o)),
        "false_alarms": int(np.sum(f & ~o)),
        "misses": int(np.sum(~f & o)),
        "correct_negatives": int(np.sum(~f & ~o)),
    }


def categorical_scores(forecast: np.ndarray, observed: np.ndarray,
                       threshold: float) -> Dict[str, Optional[float]]:
    """POD, FAR, CSI, ETS and frequency bias at one rainfall threshold."""
    t = contingency_table(forecast, observed, threshold)
    hits, fa, misses, cn = t["hits"], t["false_alarms"], t["misses"], t["correct_negatives"]
    total = hits + fa + misses + cn

    pod = _safe_div(hits, hits + misses)
    far = _safe_div(fa, hits + fa)
    csi = _safe_div(hits, hits + misses + fa)

    # Equitable Threat Score:
    #   hits_random = (hits + misses)(hits + false_alarms) / total
    #   ETS = (hits - hits_random) / (hits + misses + false_alarms - hits_random)
    ets = None
    if total > 0:
        hits_random = (hits + misses) * (hits + fa) / total
        ets = _safe_div(hits - hits_random, hits + misses + fa - hits_random)

    return {
        "threshold_mm": threshold,
        "hits": hits,
        "misses": misses,
        "false_alarms": fa,
        "correct_negatives": cn,
        "pod": _round(pod),
        "far": _round(far),
        "csi": _round(csi),
        "ets": _round(ets),
        "frequency_bias": _round(_safe_div(hits + fa, hits + misses)),
        "observed_events": hits + misses,
    }


# ----------------------------------------------------------------- spatial
def _neighbour_matrix(lat: np.ndarray, lon: np.ndarray, radius_km: float) -> np.ndarray:
    """Boolean matrix: which districts lie within ``radius_km`` of each other."""
    la = np.deg2rad(lat)[:, None]
    lo = np.deg2rad(lon)[:, None]
    dlat = la - la.T
    dlon = lo - lo.T
    a = np.sin(dlat / 2) ** 2 + np.cos(la) * np.cos(la.T) * np.sin(dlon / 2) ** 2
    dist = 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(np.clip(a, 0, 1)))
    return dist <= radius_km


def fractions_skill_score(df: pd.DataFrame, forecast_col: str, observed_col: str,
                          threshold: float, radius_km: float = 150.0) -> Optional[float]:
    """Simplified neighbourhood Fractions Skill Score.

    PROTOTYPE IMPLEMENTATION. The textbook FSS is computed on a regular
    forecast grid with square neighbourhoods. The demo data is district-point
    based, so the "neighbourhood" here is every district within
    ``radius_km`` (great-circle) of the district being scored, averaged over
    all forecast days present in ``df``. The formulation is otherwise the
    standard one:

        FSS = 1 - MSE(Pf, Po) / (mean(Pf^2) + mean(Po^2))

    where Pf/Po are neighbourhood event fractions for forecast and
    observations. With a true gridded NWP field this function is replaced by a
    grid-based neighbourhood computation - the score definition does not change.
    """
    needed = {"latitude", "longitude", forecast_col, observed_col}
    if not needed.issubset(df.columns) or df.empty:
        return None

    group_key = "date" if "date" in df.columns else None
    numerators: List[float] = []
    denominators: List[float] = []

    groups = df.groupby(group_key, sort=False) if group_key else [(None, df)]
    for _, day in groups:
        if len(day) < 2:
            continue
        lat = day["latitude"].to_numpy(float)
        lon = day["longitude"].to_numpy(float)
        nb = _neighbour_matrix(lat, lon, radius_km)
        counts = nb.sum(axis=1)
        f_bin = (day[forecast_col].to_numpy(float) >= threshold).astype(float)
        o_bin = (day[observed_col].to_numpy(float) >= threshold).astype(float)
        pf = nb @ f_bin / np.maximum(counts, 1)
        po = nb @ o_bin / np.maximum(counts, 1)
        numerators.append(float(np.mean((pf - po) ** 2)))
        denominators.append(float(np.mean(pf ** 2) + np.mean(po ** 2)))

    if not numerators:
        return None
    mse = float(np.mean(numerators))
    ref = float(np.mean(denominators))
    if ref <= 1e-12:
        # No events anywhere in forecast or observations -> FSS undefined.
        return None
    return _round(1.0 - mse / ref)


# ------------------------------------------------------------ full report
def evaluate_forecast(df: pd.DataFrame, forecast_col: str, observed_col: str,
                      thresholds: Optional[List[float]] = None,
                      fss_radius_km: float = 150.0) -> Dict:
    """Complete verification block for one forecast column."""
    thresholds = thresholds or VERIFICATION_THRESHOLDS
    f = df[forecast_col].to_numpy(float)
    o = df[observed_col].to_numpy(float)

    block: Dict = continuous_scores(f, o)
    per_threshold = {}
    for thr in thresholds:
        scores = categorical_scores(f, o, thr)
        scores["fss"] = fractions_skill_score(df, forecast_col, observed_col, thr,
                                              radius_km=fss_radius_km)
        per_threshold[str(thr)] = scores

    # Headline categorical scores use the primary "heavy rainfall" threshold
    # (the first configured threshold) so the dashboard has single numbers.
    primary = per_threshold[str(thresholds[0])]
    block.update({
        "pod": primary["pod"],
        "far": primary["far"],
        "csi": primary["csi"],
        "ets": primary["ets"],
        "fss": primary["fss"],
        "primary_threshold_mm": thresholds[0],
        "by_threshold": per_threshold,
    })
    return block


def improvement(raw: Dict, corrected: Dict) -> Dict[str, Optional[float]]:
    """Percentage improvement of the corrected forecast over the raw forecast.

    Error metrics improve when they go *down*, skill scores when they go *up*.
    Nothing here is hard-coded: everything is computed from the evaluation set.
    """
    out: Dict[str, Optional[float]] = {}
    for key in ("rmse", "mae"):
        r, c = raw.get(key), corrected.get(key)
        out[f"{key}_reduction_pct"] = (
            _round((r - c) / r * 100.0, 2) if r not in (None, 0) and c is not None else None
        )
    for key in ("csi", "pod", "ets", "fss"):
        r, c = raw.get(key), corrected.get(key)
        if r in (None, 0) or c is None:
            out[f"{key}_change_pct"] = None
        else:
            out[f"{key}_change_pct"] = _round((c - r) / abs(r) * 100.0, 2)
    r, c = raw.get("far"), corrected.get("far")
    out["far_reduction_pct"] = (
        _round((r - c) / r * 100.0, 2) if r not in (None, 0) and c is not None else None
    )
    return out


def compare(df: pd.DataFrame, raw_col: str = "raw_nwp_mm",
            corrected_col: str = "corrected_mm",
            observed_col: str = "observed_rainfall_mm",
            thresholds: Optional[List[float]] = None) -> Dict:
    """Raw NWP vs AI-corrected vs observed, in one report dictionary."""
    thresholds = thresholds or VERIFICATION_THRESHOLDS
    raw_block = evaluate_forecast(df, raw_col, observed_col, thresholds)
    ai_block = evaluate_forecast(df, corrected_col, observed_col, thresholds)
    return {
        "sample_size": int(len(df)),
        "thresholds_mm": thresholds,
        "raw_nwp": raw_block,
        "ai_corrected": ai_block,
        "improvement": improvement(raw_block, ai_block),
        "notes": [
            "The purpose of this comparison is to determine whether regime-aware "
            "post-processing improves forecast skill relative to the raw NWP forecast.",
            "FSS is a simplified district-neighbourhood prototype implementation, "
            "not a gridded neighbourhood computation.",
            "Scores are computed on synthetic demo data in DEMO MODE and are not a "
            "verification of any operational forecast system.",
        ],
    }
