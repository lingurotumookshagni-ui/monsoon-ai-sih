"""The MonsoonAI training pipeline.

Run it with ``python train_models.py`` from the ``backend/`` folder.

Stages
------
1. Build (or load) the demo dataset, and split it **by date** so the evaluation
   period is never seen in training - a random row split would leak the same
   synoptic day into both sets and inflate the scores.
2. Train the weather-regime classifier (RandomForest).
3. Train one rainfall-correction regressor per regime on the residual
   ``observed - raw_nwp``, plus a global model used as a fallback for regimes
   with too few samples.
4. Train two calibrated heavy-rainfall probability classifiers
   (>= heavy threshold, >= very-heavy threshold).
5. Evaluate everything on the held-out period, compute the raw-vs-corrected
   verification report and write all artefacts to models/ and outputs/.
"""
from __future__ import annotations

import json
from typing import Dict, Optional

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    brier_score_loss,
    classification_report,
    f1_score,
    mean_absolute_error,
    roc_auc_score,
)

from ..config import (
    DEMO_RAINFALL_CSV,
    EVAL_CSV,
    GLOBAL_CORRECTION_FILE,
    HEAVY_PROB_FILE,
    METRICS_JSON,
    MODELS_DIR,
    OUTPUTS_DIR,
    RAINFALL_THRESHOLDS,
    RANDOM_SEED,
    REGIME_CLASSIFIER_FILE,
    REGIME_MODEL_FILES,
    REGIMES,
    TRAIN_CSV,
    VERIFICATION_JSON,
    VERY_HEAVY_PROB_FILE,
)
from ..services import verification
from .features import RAINFALL_FEATURES, REGIME_FEATURES, build_features
from .registry import MonsoonModels
from .synthetic import generate_dataset

MIN_REGIME_SAMPLES = 250          # below this a regime uses the global model
HEAVY_FEATURES = RAINFALL_FEATURES + ["corrected_mm"]

try:  # optional accelerator - the project must never fail without it
    from xgboost import XGBRegressor  # type: ignore
    HAS_XGBOOST = True
except Exception:
    HAS_XGBOOST = False


def make_regressor(seed: int = RANDOM_SEED):
    """Gradient-boosted regressor; uses xgboost when installed, else sklearn."""
    if HAS_XGBOOST:
        return XGBRegressor(
            n_estimators=350, max_depth=6, learning_rate=0.06,
            subsample=0.85, colsample_bytree=0.85, reg_lambda=1.0,
            random_state=seed, n_jobs=2, tree_method="hist",
        ), "XGBRegressor"
    return HistGradientBoostingRegressor(
        max_iter=350, learning_rate=0.06, max_depth=7,
        min_samples_leaf=20, l2_regularization=1.0, random_state=seed,
    ), "HistGradientBoostingRegressor"


# ------------------------------------------------------------------ dataset
def build_dataset(n_days: int = 540, seed: int = RANDOM_SEED,
                  rebuild: bool = False) -> pd.DataFrame:
    """Load data/demo_rainfall.csv, regenerating the synthetic set if needed."""
    if DEMO_RAINFALL_CSV.exists() and not rebuild:
        df = pd.read_csv(DEMO_RAINFALL_CSV)
        if len(df) > 0 and {"raw_nwp_mm", "observed_rainfall_mm", "regime"}.issubset(df.columns):
            return df
    df = generate_dataset(n_days=n_days, seed=seed)
    DEMO_RAINFALL_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(DEMO_RAINFALL_CSV, index=False)
    return df


def split_by_date(df: pd.DataFrame, eval_fraction: float = 0.22):
    """Temporal hold-out split: the last ``eval_fraction`` of dates is evaluation."""
    if "date" not in df.columns:
        cut = int(len(df) * (1 - eval_fraction))
        return df.iloc[:cut].copy(), df.iloc[cut:].copy()
    dates = np.sort(df["date"].unique())
    cut = max(1, int(len(dates) * (1 - eval_fraction)))
    train_dates = set(dates[:cut])
    train = df[df["date"].isin(train_dates)].copy()
    test = df[~df["date"].isin(train_dates)].copy()
    return train, test


# --------------------------------------------------------- regime classifier
def train_regime_classifier(train: pd.DataFrame, test: pd.DataFrame,
                            seed: int = RANDOM_SEED) -> Dict:
    Xtr = build_features(train)[REGIME_FEATURES]
    ytr = train["regime"].astype(str)
    Xte = build_features(test)[REGIME_FEATURES]
    yte = test["regime"].astype(str)

    # 250 trees with a depth cap keeps accuracy while keeping the saved
    # artefact small enough to commit or copy around.
    clf = RandomForestClassifier(
        n_estimators=250, max_depth=20, min_samples_leaf=4,
        class_weight="balanced_subsample", n_jobs=2, random_state=seed,
    )
    clf.fit(Xtr, ytr)

    pred = clf.predict(Xte)
    bundle = {
        "model": clf,
        "features": REGIME_FEATURES,
        "classes": list(clf.classes_),
        "estimator": "RandomForestClassifier",
        "trained_on": "SYNTHETIC_DEMO",
        "note": "Regime labels are project-defined synthetic classes, not official "
                "IMD regime classifications.",
    }
    joblib.dump(bundle, MODELS_DIR / REGIME_CLASSIFIER_FILE)

    importances = sorted(
        zip(REGIME_FEATURES, clf.feature_importances_), key=lambda x: -x[1]
    )[:8]
    return {
        "accuracy": round(float(accuracy_score(yte, pred)), 4),
        "macro_f1": round(float(f1_score(yte, pred, average="macro")), 4),
        "n_train": int(len(Xtr)),
        "n_test": int(len(Xte)),
        "per_class": classification_report(yte, pred, output_dict=True, zero_division=0),
        "top_features": [{"feature": f, "importance": round(float(v), 4)} for f, v in importances],
    }


# ------------------------------------------------------- correction models
def train_correction_models(train: pd.DataFrame, test: pd.DataFrame,
                            seed: int = RANDOM_SEED) -> Dict:
    """Train the global + per-regime residual correction regressors."""
    tr = build_features(train)
    te = build_features(test)
    tr["residual"] = tr["observed_rainfall_mm"] - tr["raw_nwp_mm"]
    te["residual"] = te["observed_rainfall_mm"] - te["raw_nwp_mm"]

    report: Dict = {"regimes": {}}

    # ---- global fallback model (all regimes together) -------------------
    model, est_name = make_regressor(seed)
    model.fit(tr[RAINFALL_FEATURES], tr["residual"])
    joblib.dump({
        "model": model, "features": RAINFALL_FEATURES, "target": "residual",
        "estimator": est_name, "regime": "GLOBAL", "trained_on": "SYNTHETIC_DEMO",
    }, MODELS_DIR / GLOBAL_CORRECTION_FILE)
    report["global"] = {
        "estimator": est_name,
        "n_train": int(len(tr)),
        "test_mae_corrected": round(float(mean_absolute_error(
            te["observed_rainfall_mm"],
            np.clip(te["raw_nwp_mm"] + model.predict(te[RAINFALL_FEATURES]), 0, None))), 3),
        "test_mae_raw": round(float(mean_absolute_error(
            te["observed_rainfall_mm"], te["raw_nwp_mm"])), 3),
    }

    # ---- one model per regime ------------------------------------------
    for regime in REGIMES:
        sub_tr = tr[tr["regime"] == regime]
        sub_te = te[te["regime"] == regime]
        entry: Dict = {"n_train": int(len(sub_tr)), "n_test": int(len(sub_te))}

        if len(sub_tr) < MIN_REGIME_SAMPLES:
            # Not enough data for a dedicated model: the registry will fall
            # back to the global model for this regime.
            entry.update({"status": "skipped_insufficient_samples",
                          "min_required": MIN_REGIME_SAMPLES})
            report["regimes"][regime] = entry
            continue

        rmodel, est = make_regressor(seed)
        rmodel.fit(sub_tr[RAINFALL_FEATURES], sub_tr["residual"])
        joblib.dump({
            "model": rmodel, "features": RAINFALL_FEATURES, "target": "residual",
            "estimator": est, "regime": regime, "trained_on": "SYNTHETIC_DEMO",
            "n_train": int(len(sub_tr)),
        }, MODELS_DIR / REGIME_MODEL_FILES[regime])

        entry["status"] = "trained"
        entry["estimator"] = est
        if len(sub_te) > 0:
            corrected = np.clip(sub_te["raw_nwp_mm"] + rmodel.predict(sub_te[RAINFALL_FEATURES]), 0, None)
            raw_mae = float(mean_absolute_error(sub_te["observed_rainfall_mm"], sub_te["raw_nwp_mm"]))
            cor_mae = float(mean_absolute_error(sub_te["observed_rainfall_mm"], corrected))
            entry.update({
                "test_mae_raw": round(raw_mae, 3),
                "test_mae_corrected": round(cor_mae, 3),
                "mae_reduction_pct": round((raw_mae - cor_mae) / raw_mae * 100, 2) if raw_mae else None,
                "mean_correction_mm": round(float(np.mean(corrected - sub_te["raw_nwp_mm"])), 2),
            })
        report["regimes"][regime] = entry

    return report


# ----------------------------------------------- heavy rainfall probability
def train_heavy_probability(train: pd.DataFrame, test: pd.DataFrame,
                            engine: MonsoonModels, seed: int = RANDOM_SEED) -> Dict:
    """Two calibrated binary classifiers: P(>= heavy) and P(>= very heavy).

    Both are conditioned on the *corrected* rainfall estimate, so the
    probability product benefits from the regime-aware post-processing. The
    corrected value on the training rows is an in-sample prediction of the
    correction models, which is noted as a known prototype limitation.
    """
    def prepare(df: pd.DataFrame) -> pd.DataFrame:
        feats = build_features(df)
        corr = engine.apply_correction(feats)
        feats = feats.copy()
        feats["corrected_mm"] = corr["corrected_mm"].to_numpy(float)
        return feats

    tr, te = prepare(train), prepare(test)
    report: Dict = {}

    targets = {
        HEAVY_PROB_FILE: ("heavy", RAINFALL_THRESHOLDS["HEAVY_MIN"]),
        VERY_HEAVY_PROB_FILE: ("very_heavy", RAINFALL_THRESHOLDS["VERY_HEAVY_MIN"]),
    }

    for fname, (name, threshold) in targets.items():
        ytr = (tr["observed_rainfall_mm"] >= threshold).astype(int)
        yte = (te["observed_rainfall_mm"] >= threshold).astype(int)

        base = RandomForestClassifier(
            n_estimators=150, max_depth=18, min_samples_leaf=10,
            class_weight="balanced_subsample", n_jobs=2, random_state=seed,
        )
        # Random-forest vote fractions are not calibrated probabilities;
        # isotonic calibration on cross-validated folds fixes that, which
        # matters a lot for a probability product used for warnings.
        if ytr.sum() >= 50 and (len(ytr) - ytr.sum()) >= 50:
            model = CalibratedClassifierCV(base, method="isotonic", cv=3)
            calibrated = True
        else:
            model = base
            calibrated = False
        model.fit(tr[HEAVY_FEATURES], ytr)

        joblib.dump({
            "model": model, "features": HEAVY_FEATURES, "threshold_mm": threshold,
            "estimator": "CalibratedClassifierCV(RandomForest, isotonic)" if calibrated
                         else "RandomForestClassifier",
            "calibrated": calibrated, "trained_on": "SYNTHETIC_DEMO",
        }, MODELS_DIR / fname)

        p = model.predict_proba(te[HEAVY_FEATURES])[:, list(model.classes_).index(1)] \
            if 1 in list(model.classes_) else np.zeros(len(te))
        entry = {
            "threshold_mm": threshold,
            "calibrated": calibrated,
            "positive_rate_train": round(float(ytr.mean()), 4),
            "positive_rate_test": round(float(yte.mean()), 4),
            "brier_score": round(float(brier_score_loss(yte, p)), 4) if len(np.unique(yte)) > 1 else None,
            "roc_auc": round(float(roc_auc_score(yte, p)), 4) if len(np.unique(yte)) > 1 else None,
        }
        report[name] = entry

    return report


# ------------------------------------------------------------- evaluation
def evaluate(test: pd.DataFrame, engine: MonsoonModels) -> Dict:
    """Run the full live pipeline on the hold-out period and verify it."""
    processed = engine.process(test.drop(columns=["regime"], errors="ignore"))
    processed["observed_rainfall_mm"] = test["observed_rainfall_mm"].to_numpy(float)
    if "regime" in test.columns:
        processed["true_regime_synthetic"] = test["regime"].to_numpy()
    keep = [c for c in [
        "date", "district", "state", "latitude", "longitude", "elevation",
        "distance_from_coast", "month", "day_of_year", "humidity", "temperature",
        "pressure", "wind_speed", "wind_direction", "regime", "regime_confidence",
        "true_regime_synthetic", "raw_nwp_mm", "corrected_mm", "correction_mm",
        "observed_rainfall_mm", "heavy_probability", "very_heavy_probability",
        "category", "risk_band",
    ] if c in processed.columns]
    out = processed[keep]
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    out.to_csv(EVAL_CSV, index=False)

    report = verification.compare(out)
    report["data_source"] = "SYNTHETIC_DEMO"
    with open(VERIFICATION_JSON, "w") as fh:
        json.dump(report, fh, indent=2)
    return report


# ------------------------------------------------------------------- driver
def run_pipeline(n_days: int = 540, seed: int = RANDOM_SEED,
                 rebuild_data: bool = False, verbose: bool = True) -> Dict:
    def say(*a):
        if verbose:
            print(*a, flush=True)

    say("=" * 68)
    say("MonsoonAI training pipeline  (DEMO MODE - synthetic data)")
    say("=" * 68)

    say("[1/6] Building dataset ...")
    df = build_dataset(n_days=n_days, seed=seed, rebuild=rebuild_data)
    train, test = split_by_date(df)
    train.to_csv(TRAIN_CSV, index=False)
    say(f"      rows={len(df)}  train={len(train)}  holdout={len(test)}  "
        f"districts={df['district'].nunique()}")
    say(f"      xgboost available: {HAS_XGBOOST}")

    say("[2/6] Training weather regime classifier ...")
    regime_report = train_regime_classifier(train, test, seed)
    say(f"      accuracy={regime_report['accuracy']}  macro_f1={regime_report['macro_f1']}")

    say("[3/6] Training regime-specific rainfall correction models ...")
    correction_report = train_correction_models(train, test, seed)
    for regime, entry in correction_report["regimes"].items():
        if entry.get("status") == "trained":
            say(f"      {regime:<22} MAE raw={entry.get('test_mae_raw')} -> "
                f"corrected={entry.get('test_mae_corrected')} "
                f"({entry.get('mae_reduction_pct')}% better)")
        else:
            say(f"      {regime:<22} {entry.get('status')} (n={entry['n_train']}) "
                f"-> global model used")

    engine = MonsoonModels()   # reload artefacts written so far

    say("[4/6] Training heavy rainfall probability models ...")
    heavy_report = train_heavy_probability(train, test, engine, seed)
    for name, entry in heavy_report.items():
        say(f"      {name:<12} threshold={entry['threshold_mm']}mm  "
            f"AUC={entry['roc_auc']}  Brier={entry['brier_score']}  "
            f"calibrated={entry['calibrated']}")

    engine = MonsoonModels()   # reload again, now including probability models

    say("[5/6] Evaluating full pipeline on the hold-out period ...")
    ver = evaluate(test, engine)
    raw, ai = ver["raw_nwp"], ver["ai_corrected"]
    say(f"      RMSE  raw={raw['rmse']}  corrected={ai['rmse']}  "
        f"({ver['improvement']['rmse_reduction_pct']}% reduction)")
    say(f"      MAE   raw={raw['mae']}  corrected={ai['mae']}  "
        f"({ver['improvement']['mae_reduction_pct']}% reduction)")
    say(f"      @{raw['primary_threshold_mm']}mm  CSI {raw['csi']} -> {ai['csi']}   "
        f"POD {raw['pod']} -> {ai['pod']}   FAR {raw['far']} -> {ai['far']}")
    say(f"                ETS {raw['ets']} -> {ai['ets']}   FSS {raw['fss']} -> {ai['fss']}")

    metrics = {
        "data": {
            "rows": int(len(df)), "train_rows": int(len(train)),
            "holdout_rows": int(len(test)),
            "districts": int(df["district"].nunique()),
            "source": "SYNTHETIC_DEMO",
        },
        "xgboost_available": HAS_XGBOOST,
        "regime_classifier": regime_report,
        "correction_models": correction_report,
        "heavy_rainfall_probability": heavy_report,
        "verification": ver,
    }
    say("[6/6] Writing artefacts ...")
    with open(METRICS_JSON, "w") as fh:
        json.dump(metrics, fh, indent=2, default=str)
    say(f"      models   -> {MODELS_DIR}")
    say(f"      outputs  -> {OUTPUTS_DIR}")
    say("Done. Start the API with: uvicorn app.main:app --reload --port 8000")
    return metrics


def load_metrics() -> Optional[Dict]:
    if METRICS_JSON.exists():
        try:
            with open(METRICS_JSON) as fh:
                return json.load(fh)
        except Exception:
            return None
    return None
