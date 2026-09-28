"""Model registry and inference engine.

Loads every artefact produced by ``train_models.py`` once at process start and
exposes vectorised inference helpers used by all API routes:

    predict_regime()        -> regime classification + probabilities
    apply_correction()      -> regime-specific bias-corrected rainfall
    heavy_probabilities()   -> P(heavy), P(very heavy)
    process()              -> the full pipeline over a DataFrame

If an artefact is missing the engine transparently falls back to the
deterministic heuristics in ``app/ml/rules.py`` and marks the result with
``method="heuristic_fallback"`` so the dashboard never silently presents a
heuristic as a model output.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

import joblib
import numpy as np
import pandas as pd

from ..config import (
    GLOBAL_CORRECTION_FILE,
    HEAVY_PROB_FILE,
    MODELS_DIR,
    RAINFALL_THRESHOLDS,
    REGIME_CLASSIFIER_FILE,
    REGIME_MODEL_FILES,
    REGIMES,
    VERY_HEAVY_PROB_FILE,
)
from ..utils.categories import public_condition, rainfall_category, risk_band
from . import rules
from .features import RAINFALL_FEATURES, REGIME_FEATURES, build_features


def _load(path: Path):
    try:
        return joblib.load(path) if path.exists() else None
    except Exception:  # corrupt/incompatible artefact -> fall back, never crash
        return None


class MonsoonModels:
    """Holds all trained artefacts for the running API process."""

    def __init__(self, models_dir: Path = MODELS_DIR):
        self.models_dir = Path(models_dir)
        self.regime_clf = None
        self.correction: Dict[str, dict] = {}
        self.global_correction = None
        self.heavy = None
        self.very_heavy = None
        self.load()

    # ------------------------------------------------------------- loading
    def load(self) -> None:
        self.regime_clf = _load(self.models_dir / REGIME_CLASSIFIER_FILE)
        self.global_correction = _load(self.models_dir / GLOBAL_CORRECTION_FILE)
        self.heavy = _load(self.models_dir / HEAVY_PROB_FILE)
        self.very_heavy = _load(self.models_dir / VERY_HEAVY_PROB_FILE)
        self.correction = {}
        for regime, fname in REGIME_MODEL_FILES.items():
            bundle = _load(self.models_dir / fname)
            if bundle is not None:
                self.correction[regime] = bundle

    @property
    def trained(self) -> bool:
        return self.regime_clf is not None and bool(self.correction)

    def info(self) -> Dict:
        return {
            "models_dir": str(self.models_dir),
            "regime_classifier_loaded": self.regime_clf is not None,
            "regime_correction_models": sorted(self.correction.keys()),
            "global_correction_model_loaded": self.global_correction is not None,
            "heavy_probability_model_loaded": self.heavy is not None,
            "very_heavy_probability_model_loaded": self.very_heavy is not None,
            "mode": "trained_models" if self.trained else "heuristic_fallback",
        }

    # ------------------------------------------------------------- regime
    def predict_regime(self, df: pd.DataFrame) -> pd.DataFrame:
        """Classify the prevailing weather regime for every row of ``df``."""
        feats = build_features(df)
        n = len(feats)

        if self.regime_clf is not None:
            model = self.regime_clf["model"]
            classes = list(self.regime_clf["classes"])
            proba = model.predict_proba(feats[self.regime_clf.get("features", REGIME_FEATURES)])
            best = proba.argmax(axis=1)
            regimes = [classes[i] for i in best]
            conf = proba.max(axis=1)
            prob_dicts = [
                {classes[j]: round(float(proba[i, j]), 4) for j in range(len(classes))}
                for i in range(n)
            ]
            method = "random_forest_classifier"
        else:
            prob_dicts, regimes, conf = [], [], []
            for _, row in feats.iterrows():
                scores = rules.diagnose_regime(row.to_dict())
                ordered = {k: round(float(scores.get(k, 0.0)), 4) for k in REGIMES}
                top = max(ordered, key=ordered.get)
                prob_dicts.append(ordered)
                regimes.append(top)
                conf.append(ordered[top])
            conf = np.asarray(conf, dtype=float)
            method = "heuristic_fallback"

        return pd.DataFrame({
            "regime": regimes,
            "regime_confidence": np.round(np.asarray(conf, dtype=float), 4),
            "regime_probabilities": prob_dicts,
            "regime_method": [method] * n,
        }, index=df.index)

    # --------------------------------------------------------- correction
    def apply_correction(self, df: pd.DataFrame) -> pd.DataFrame:
        """Regime-specific bias correction of the raw NWP rainfall.

        Each regime has its own regressor trained on the *residual*
        (observed - raw NWP). The residual target is easier to learn than the
        absolute amount because the model only has to explain the model error,
        and it degrades gracefully: a zero prediction simply returns the raw
        forecast. Corrected rainfall is clipped at 0 mm.
        """
        feats = build_features(df)
        raw = feats["raw_nwp_mm"].to_numpy(float)
        corrected = np.array(raw, dtype=float, copy=True)
        methods: List[str] = ["raw_passthrough"] * len(feats)
        regimes = feats["regime"].astype(str) if "regime" in feats.columns else pd.Series(
            ["NORMAL_MONSOON"] * len(feats), index=feats.index)

        for regime in regimes.unique():
            mask = (regimes == regime).to_numpy()
            if not mask.any():
                continue
            bundle = self.correction.get(regime) or self.global_correction
            if bundle is not None:
                cols = bundle.get("features", RAINFALL_FEATURES)
                X = feats.loc[mask, cols]
                pred = np.asarray(bundle["model"].predict(X), dtype=float)
                if bundle.get("target", "residual") == "residual":
                    corrected[mask] = raw[mask] + pred
                else:
                    corrected[mask] = pred
                used = "regime_model" if regime in self.correction else "global_model"
                label = f"{used}:{bundle.get('estimator', 'unknown')}"
            else:
                corrected[mask] = [
                    rules.fallback_correction(r, regime, e, c)
                    for r, e, c in zip(
                        raw[mask],
                        feats.loc[mask, "elevation"].to_numpy(float),
                        feats.loc[mask, "distance_from_coast"].to_numpy(float),
                    )
                ]
                label = "heuristic_fallback"
            for i in np.where(mask)[0]:
                methods[i] = label

        corrected = np.clip(corrected, 0.0, None)  # rainfall can never be negative
        return pd.DataFrame({
            "raw_nwp_mm": np.round(raw, 2),
            "corrected_mm": np.round(corrected, 2),
            "correction_mm": np.round(corrected - raw, 2),
            "correction_method": methods,
        }, index=df.index)

    # ------------------------------------------------------ heavy rainfall
    def heavy_probabilities(self, df: pd.DataFrame,
                            corrected: Optional[np.ndarray] = None) -> pd.DataFrame:
        """P(rainfall >= heavy) and P(rainfall >= very heavy).

        The classifiers are trained on the same features as the correction
        models plus the corrected rainfall estimate, so the probability is
        conditioned on the post-processed amount rather than the raw forecast.
        """
        feats = build_features(df)
        if corrected is not None:
            feats = feats.copy()
            feats["corrected_mm"] = np.asarray(corrected, dtype=float)
        elif "corrected_mm" not in feats.columns:
            feats["corrected_mm"] = feats["raw_nwp_mm"]

        def _proba(bundle, threshold):
            if bundle is None:
                return None, "heuristic_fallback"
            cols = bundle.get("features")
            X = feats[cols]
            p = bundle["model"].predict_proba(X)
            # Positive class may not be present if training data was degenerate.
            classes = list(getattr(bundle["model"], "classes_", [0, 1]))
            if 1 in classes:
                p1 = p[:, classes.index(1)]
            else:
                p1 = np.zeros(len(feats))
            return np.clip(p1, 0.0, 1.0), f"calibrated_classifier@{threshold}mm"

        p_heavy, m_heavy = _proba(self.heavy, RAINFALL_THRESHOLDS["HEAVY_MIN"])
        p_very, m_very = _proba(self.very_heavy, RAINFALL_THRESHOLDS["VERY_HEAVY_MIN"])

        amounts = feats["corrected_mm"].to_numpy(float)
        if p_heavy is None:
            p_heavy = np.array([rules.fallback_heavy_probability(a, RAINFALL_THRESHOLDS["HEAVY_MIN"])
                                for a in amounts])
        if p_very is None:
            p_very = np.array([rules.fallback_heavy_probability(a, RAINFALL_THRESHOLDS["VERY_HEAVY_MIN"])
                               for a in amounts])
        # Monotonicity guard: P(very heavy) can never exceed P(heavy).
        p_very = np.minimum(p_very, p_heavy)

        return pd.DataFrame({
            "heavy_probability": np.round(p_heavy, 4),
            "very_heavy_probability": np.round(p_very, 4),
            "heavy_probability_method": [m_heavy] * len(feats),
            "very_heavy_probability_method": [m_very] * len(feats),
        }, index=df.index)

    # --------------------------------------------------------- full pipeline
    def process(self, df: pd.DataFrame, use_given_regime: bool = False) -> pd.DataFrame:
        """Run classify -> correct -> heavy probability over a DataFrame."""
        work = df.copy()
        if use_given_regime and "regime" in work.columns:
            regime_block = pd.DataFrame({
                "regime": work["regime"].astype(str),
                "regime_confidence": work.get("regime_confidence", 1.0),
                "regime_probabilities": [{} for _ in range(len(work))],
                "regime_method": ["provided"] * len(work),
            }, index=work.index)
        else:
            regime_block = self.predict_regime(work)

        work = work.drop(columns=[c for c in regime_block.columns if c in work.columns])
        work = pd.concat([work, regime_block], axis=1)

        corr = self.apply_correction(work)
        work = work.drop(columns=[c for c in corr.columns if c in work.columns])
        work = pd.concat([work, corr], axis=1)

        probs = self.heavy_probabilities(work, corrected=work["corrected_mm"].to_numpy(float))
        work = pd.concat([work, probs], axis=1)

        work["category"] = [rainfall_category(v) for v in work["corrected_mm"]]
        work["raw_category"] = [rainfall_category(v) for v in work["raw_nwp_mm"]]
        work["risk_band"] = [risk_band(p) for p in work["heavy_probability"]]
        # Plain-language band shown to non-specialist users (same thresholds).
        work["condition"] = [public_condition(v) for v in work["corrected_mm"]]
        return work


_ENGINE: Optional[MonsoonModels] = None


def get_engine(reload: bool = False) -> MonsoonModels:
    """Process-wide singleton so models are loaded from disk only once."""
    global _ENGINE
    if _ENGINE is None or reload:
        _ENGINE = MonsoonModels()
    return _ENGINE
