"""Tests for the ML core: features, synthetic data, inference, metrics.

These run without FastAPI installed:  python -m pytest tests/test_core.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.config import REGIMES
from app.ml.features import RAINFALL_FEATURES, REGIME_FEATURES, build_features
from app.ml.registry import MonsoonModels
from app.ml.rules import diagnose_regime, fallback_correction
from app.ml.synthetic import generate_dataset, generate_forecast_snapshot, load_districts
from app.services import verification
from app.services.uploads import UploadValidationError, parse_and_validate
from app.utils.categories import public_condition, rainfall_category, risk_band


# ---------------------------------------------------------------- districts
def test_districts_have_required_columns():
    df = load_districts()
    assert len(df) >= 50
    for col in ["district", "state", "latitude", "longitude", "elevation",
                "distance_from_coast"]:
        assert col in df.columns
    assert df["latitude"].between(6, 37).all()
    assert df["longitude"].between(68, 98).all()


# ----------------------------------------------------------------- features
def test_build_features_fills_defaults_and_derived_columns():
    feats = build_features(pd.DataFrame([{"raw_nwp_mm": 50.0}]))
    for col in REGIME_FEATURES + ["regime_code"]:
        assert col in feats.columns
    assert np.isclose(feats["log_raw_nwp"].iloc[0], np.log1p(50.0))
    assert abs(feats["wind_dir_sin"].iloc[0] ** 2 + feats["wind_dir_cos"].iloc[0] ** 2 - 1) < 1e-9


def test_feature_lists_are_consistent():
    assert RAINFALL_FEATURES[:len(REGIME_FEATURES)] == REGIME_FEATURES
    assert "regime_code" in RAINFALL_FEATURES


# ---------------------------------------------------------------- synthetic
def test_synthetic_dataset_is_plausible():
    df = generate_dataset(n_days=20, seed=7)
    assert len(df) > 0
    assert (df["observed_rainfall_mm"] >= 0).all()
    assert (df["raw_nwp_mm"] >= 0).all()
    assert set(df["regime"].unique()).issubset(set(REGIMES))
    # Break spells must be drier than active spells on average.
    means = df.groupby("regime")["observed_rainfall_mm"].mean()
    if {"ACTIVE_MONSOON", "BREAK_MONSOON"}.issubset(means.index):
        assert means["BREAK_MONSOON"] < means["ACTIVE_MONSOON"]
    # The demo NWP error model must under-forecast orographic rainfall.
    oro = df[df["regime"] == "OROGRAPHIC_RAINFALL"]
    if len(oro) > 30:
        assert oro["raw_nwp_mm"].mean() < oro["observed_rainfall_mm"].mean()


def test_forecast_snapshot_is_deterministic_per_date():
    import datetime as dt
    day = dt.date(2024, 7, 15)
    a = generate_forecast_snapshot(for_date=day)
    b = generate_forecast_snapshot(for_date=day)
    assert a["raw_nwp_mm"].tolist() == b["raw_nwp_mm"].tolist()
    assert len(a) == len(load_districts())


# --------------------------------------------------------------- categories
@pytest.mark.parametrize("mm,expected", [
    (0, "LIGHT"), (14.9, "LIGHT"), (15, "MODERATE"), (64.4, "MODERATE"),
    (64.5, "HEAVY"), (115.5, "HEAVY"), (115.6, "VERY_HEAVY"),
    (204.4, "VERY_HEAVY"), (204.5, "EXTREMELY_HEAVY"), (500, "EXTREMELY_HEAVY"),
])
def test_rainfall_category_boundaries(mm, expected):
    assert rainfall_category(mm) == expected


@pytest.mark.parametrize("mm,expected", [
    (0, "LOW"), (4.9, "LOW"), (5, "NORMAL"), (14.9, "NORMAL"),
    (15, "MODERATE"), (64.4, "MODERATE"), (64.5, "HEAVY"),
    (115.5, "HEAVY"), (115.6, "VERY_HEAVY"), (300, "VERY_HEAVY"),
])
def test_public_condition_bands(mm, expected):
    """The citizen-facing scale must stay aligned with the operational thresholds."""
    assert public_condition(mm) == expected


def test_pipeline_adds_public_condition():
    engine = MonsoonModels()
    out = engine.process(generate_forecast_snapshot().drop(
        columns=["true_regime_synthetic"], errors="ignore"))
    assert out["condition"].isin(
        ["LOW", "NORMAL", "MODERATE", "HEAVY", "VERY_HEAVY"]).all()


def test_risk_bands():
    assert risk_band(0.9) == "VERY_HIGH"
    assert risk_band(0.5) == "HIGH"
    assert risk_band(0.25) == "MODERATE"
    assert risk_band(0.01) == "LOW"


# -------------------------------------------------------------------- rules
def test_heuristic_regime_scores_sum_to_one():
    scores = diagnose_regime({"humidity": 94, "pressure": 990, "wind_speed": 17,
                              "raw_nwp_mm": 120, "month": 7, "latitude": 20,
                              "elevation": 50, "distance_from_coast": 30,
                              "temperature": 25})
    assert abs(sum(scores.values()) - 1.0) < 1e-9
    assert set(scores.keys()) == set(REGIMES)


def test_fallback_correction_is_never_negative():
    for regime in REGIMES:
        assert fallback_correction(0.0, regime, 1200, 10) >= 0.0


# ----------------------------------------------------------------- pipeline
def test_engine_pipeline_end_to_end():
    engine = MonsoonModels()
    df = generate_forecast_snapshot()
    out = engine.process(df.drop(columns=["true_regime_synthetic"], errors="ignore"))
    assert len(out) == len(df)
    assert (out["corrected_mm"] >= 0).all()
    assert out["regime"].isin(REGIMES).all()
    assert out["heavy_probability"].between(0, 1).all()
    assert out["very_heavy_probability"].between(0, 1).all()
    # Monotonicity: P(very heavy) <= P(heavy)
    assert (out["very_heavy_probability"] <= out["heavy_probability"] + 1e-9).all()
    assert out["category"].isin(["LIGHT", "MODERATE", "HEAVY", "VERY_HEAVY",
                                 "EXTREMELY_HEAVY"]).all()


# ------------------------------------------------------------- verification
def test_contingency_and_scores_are_correct():
    fc = np.array([100.0, 100.0, 10.0, 10.0])
    ob = np.array([100.0, 10.0, 100.0, 10.0])
    t = verification.contingency_table(fc, ob, 64.5)
    assert (t["hits"], t["false_alarms"], t["misses"], t["correct_negatives"]) == (1, 1, 1, 1)
    s = verification.categorical_scores(fc, ob, 64.5)
    assert s["pod"] == 0.5 and s["far"] == 0.5
    assert abs(s["csi"] - 1 / 3) < 1e-3   # score is rounded to 4 dp
    assert s["ets"] is not None


def test_scores_handle_no_events_without_dividing_by_zero():
    fc = np.zeros(10)
    ob = np.zeros(10)
    s = verification.categorical_scores(fc, ob, 64.5)
    assert s["pod"] is None and s["far"] is None and s["csi"] is None
    c = verification.continuous_scores(fc, ob)
    assert c["rmse"] == 0.0


def test_perfect_forecast_gets_perfect_scores():
    ob = np.array([0.0, 20.0, 80.0, 150.0, 260.0])
    s = verification.categorical_scores(ob, ob, 64.5)
    assert s["pod"] == 1.0 and s["far"] == 0.0 and s["csi"] == 1.0
    assert verification.continuous_scores(ob, ob)["rmse"] == 0.0


def test_fss_between_zero_and_one_and_perfect_when_identical():
    df = generate_dataset(n_days=4, seed=3)
    df["corrected_mm"] = df["observed_rainfall_mm"]
    perfect = verification.fractions_skill_score(df, "corrected_mm",
                                                "observed_rainfall_mm", 64.5)
    assert perfect is None or abs(perfect - 1.0) < 1e-6
    raw_fss = verification.fractions_skill_score(df, "raw_nwp_mm",
                                                 "observed_rainfall_mm", 64.5)
    assert raw_fss is None or -1.0 <= raw_fss <= 1.0


def test_compare_report_structure():
    df = generate_dataset(n_days=10, seed=11)
    engine = MonsoonModels()
    processed = engine.process(df.drop(columns=["regime"]))
    processed["observed_rainfall_mm"] = df["observed_rainfall_mm"].to_numpy()
    report = verification.compare(processed)
    for block in ("raw_nwp", "ai_corrected"):
        for key in ("rmse", "mae", "csi", "pod", "far", "ets", "fss"):
            assert key in report[block]
    assert "improvement" in report
    assert report["sample_size"] == len(df)


# ------------------------------------------------------------------ uploads
def test_upload_rejects_missing_required_columns():
    csv = b"district,state\nKasaragod,Kerala\n"
    with pytest.raises(UploadValidationError) as exc:
        parse_and_validate(csv)
    assert any("latitude" in e for e in exc.value.errors)


def test_upload_accepts_minimal_valid_csv_and_clips_ranges():
    csv = (b"district,latitude,longitude,raw_nwp_mm,humidity\n"
           b"Kasaragod,12.5,74.99,82,140\n"
           b"Kannur,11.87,75.37,60,90\n")
    df, summary = parse_and_validate(csv)
    assert summary["rows_accepted"] == 2
    assert df["humidity"].max() <= 100     # clipped
    assert summary["has_observations"] is False
    assert any("humidity" in w for w in summary["warnings"])


def test_upload_rejects_empty_file():
    with pytest.raises(UploadValidationError):
        parse_and_validate(b"")
