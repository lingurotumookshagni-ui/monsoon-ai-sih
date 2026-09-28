"""Synthetic monsoon dataset generator for MonsoonAI demo mode.

WHAT THIS IS
------------
A physically *plausible* but entirely **synthetic** generator. It produces
district-level pseudo-observations, pseudo-NWP forecasts and regime labels so
that the whole system (classifier, regime-specific correction, heavy-rain
probability, verification) can be trained and demonstrated with no external
data, no API keys and no database.

WHAT THIS IS NOT
----------------
It is not real weather data, and the regime labels are **not** official
meteorological regime classifications. They are labels of this project's own
generative process. When real NWP output, rain-gauge/satellite observations and
expert regime definitions are available, this module is simply replaced - see
`app/services/datasets.py` and the README section "Replacing demo data with
real data".

HOW THE GENERATOR WORKS
-----------------------
1. A daily "synoptic state" is drawn (active spell / break spell / low-pressure
   system / quiet), which shifts regime probabilities for the whole country on
   that day - this creates day-to-day spatial coherence instead of pure noise.
2. For every district, regime probabilities are weighted by geography
   (distance from coast, elevation, latitude) and by calendar month, then a
   regime is sampled.
3. Meteorological features are drawn from regime-conditional distributions
   (humidity, temperature, station pressure reduced for elevation, wind speed
   and direction).
4. "Observed" rainfall is drawn from a gamma distribution whose mean depends on
   the regime, orographic enhancement and coastal proximity - giving a
   realistic right-skewed rainfall distribution with a heavy tail.
5. The "raw NWP forecast" is produced from the observation by applying a
   regime-dependent error model: models under-forecast orographic and coastal
   heavy rain, displace depression rainfall, and over-forecast drizzle during
   break spells. This deterministic-plus-noise error structure is exactly what
   the regime-aware post-processing models have to learn.
"""
from __future__ import annotations

import datetime as dt
from typing import Optional

import numpy as np
import pandas as pd

from ..config import DISTRICTS_CSV, RANDOM_SEED, REGIMES

# Regime-conditional feature means / spreads.
# (humidity %, temperature degC, mean-sea-level pressure hPa, wind m/s, wind dir deg)
REGIME_FEATURE_STATS = {
    "ACTIVE_MONSOON":      dict(rh=(88, 4), t=(26.0, 1.8), p=(998.0, 2.0), ws=(11.0, 2.5), wd=(245, 18)),
    "BREAK_MONSOON":       dict(rh=(60, 7), t=(33.5, 2.2), p=(1006.0, 2.0), ws=(4.0, 1.5), wd=(300, 40)),
    "MONSOON_DEPRESSION":  dict(rh=(93, 3), t=(25.0, 1.5), p=(991.0, 2.5), ws=(16.0, 3.5), wd=(200, 25)),
    "COASTAL_RAINFALL":    dict(rh=(86, 4), t=(27.8, 1.5), p=(1002.0, 1.8), ws=(9.0, 2.2), wd=(262, 15)),
    "OROGRAPHIC_RAINFALL": dict(rh=(90, 4), t=(21.5, 3.0), p=(1000.0, 2.0), ws=(8.5, 2.5), wd=(250, 20)),
    "WESTERN_DISTURBANCE": dict(rh=(70, 8), t=(12.5, 4.0), p=(1012.0, 3.0), ws=(7.0, 2.5), wd=(292, 30)),
    "NORMAL_MONSOON":      dict(rh=(76, 6), t=(29.0, 2.0), p=(1004.0, 2.0), ws=(6.0, 2.0), wd=(240, 30)),
}

# Regime-conditional rainfall statistics.
#   base  : mean 24 h rainfall (mm) before geographic enhancement
#   dry_p : probability the day is completely dry in that regime
#   shape : gamma shape parameter (smaller -> heavier tail)
REGIME_RAIN_STATS = {
    "ACTIVE_MONSOON":      dict(base=42.0, dry_p=0.05, shape=1.10),
    "BREAK_MONSOON":       dict(base=3.0,  dry_p=0.55, shape=0.80),
    "MONSOON_DEPRESSION":  dict(base=95.0, dry_p=0.02, shape=1.30),
    "COASTAL_RAINFALL":    dict(base=52.0, dry_p=0.07, shape=1.00),
    "OROGRAPHIC_RAINFALL": dict(base=58.0, dry_p=0.06, shape=1.15),
    "WESTERN_DISTURBANCE": dict(base=14.0, dry_p=0.25, shape=0.95),
    "NORMAL_MONSOON":      dict(base=13.0, dry_p=0.30, shape=0.90),
}

# NWP error model per regime: raw = obs * mult + add, then noise.
#   mult  : systematic multiplicative bias of the raw forecast
#   add   : systematic additive bias (mm)
#   sigma : lognormal multiplicative noise (forecast "randomness")
#   jitter: additive Gaussian noise (mm)
REGIME_NWP_ERROR = {
    "ACTIVE_MONSOON":      dict(mult=0.86, add=1.5, sigma=0.28, jitter=3.0),
    "BREAK_MONSOON":       dict(mult=1.15, add=4.5, sigma=0.35, jitter=2.0),
    "MONSOON_DEPRESSION":  dict(mult=0.70, add=2.0, sigma=0.45, jitter=8.0),
    "COASTAL_RAINFALL":    dict(mult=0.74, add=2.0, sigma=0.30, jitter=4.0),
    "OROGRAPHIC_RAINFALL": dict(mult=0.55, add=1.5, sigma=0.32, jitter=4.0),
    "WESTERN_DISTURBANCE": dict(mult=0.88, add=2.5, sigma=0.30, jitter=2.5),
    "NORMAL_MONSOON":      dict(mult=0.95, add=1.5, sigma=0.25, jitter=2.0),
}

SYNOPTIC_STATES = ["ACTIVE_SPELL", "BREAK_SPELL", "LOW_PRESSURE_SYSTEM", "QUIET"]


def load_districts(path=None) -> pd.DataFrame:
    """Load the district metadata table (approximate geography, demo use)."""
    df = pd.read_csv(path or DISTRICTS_CSV)
    required = {"district", "state", "latitude", "longitude", "elevation",
                "distance_from_coast"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"districts.csv is missing columns: {sorted(missing)}")
    return df


def _regime_weights(d: pd.DataFrame, month: int, synoptic: str) -> np.ndarray:
    """Geography- and season-dependent regime weights, shape (n_districts, 7)."""
    n = len(d)
    elev = d["elevation"].to_numpy(float)
    coast = d["distance_from_coast"].to_numpy(float)
    lat = d["latitude"].to_numpy(float)
    lon = d["longitude"].to_numpy(float)

    coastal_prox = np.exp(-coast / 45.0)            # 1 at the shore, ~0 inland
    orographic = np.clip((elev - 350.0) / 900.0, 0, 2.2)
    north = np.clip((lat - 26.0) / 4.0, 0, 1.5)     # NW India / western Himalaya
    monsoon_core = np.exp(-((lat - 20.0) ** 2) / 90.0)
    east_side = np.clip((lon - 78.0) / 8.0, 0, 1.4)  # Bay of Bengal influence

    monsoon_season = 1.0 if month in (6, 7, 8, 9) else 0.0
    shoulder = 1.0 if month in (5, 10) else 0.0
    winter = 1.0 if month in (11, 12, 1, 2, 3, 4) else 0.0

    w = np.zeros((n, len(REGIMES)))
    idx = {r: i for i, r in enumerate(REGIMES)}

    w[:, idx["ACTIVE_MONSOON"]] = (1.4 * monsoon_season + 0.3 * shoulder) * (0.5 + monsoon_core)
    w[:, idx["BREAK_MONSOON"]] = (1.0 * monsoon_season + 0.2 * shoulder) * (0.4 + 0.9 * (1 - coastal_prox))
    w[:, idx["MONSOON_DEPRESSION"]] = (0.55 * monsoon_season + 0.25 * shoulder) * (0.25 + east_side) * (0.4 + monsoon_core)
    w[:, idx["COASTAL_RAINFALL"]] = (0.9 * monsoon_season + 0.5 * shoulder + 0.25 * winter) * (0.1 + 2.2 * coastal_prox)
    w[:, idx["OROGRAPHIC_RAINFALL"]] = (1.0 * monsoon_season + 0.4 * shoulder + 0.25 * winter) * (0.05 + orographic)
    w[:, idx["WESTERN_DISTURBANCE"]] = (1.6 * winter + 0.15 * shoulder) * (0.02 + north + 0.4 * np.clip(elev / 2000.0, 0, 1.2))
    w[:, idx["NORMAL_MONSOON"]] = 0.9 + 0.4 * winter

    # Daily synoptic state nudges the whole country in the same direction.
    if synoptic == "ACTIVE_SPELL":
        w[:, idx["ACTIVE_MONSOON"]] *= 3.0
        w[:, idx["BREAK_MONSOON"]] *= 0.2
    elif synoptic == "BREAK_SPELL":
        w[:, idx["BREAK_MONSOON"]] *= 3.2
        w[:, idx["ACTIVE_MONSOON"]] *= 0.2
        w[:, idx["MONSOON_DEPRESSION"]] *= 0.3
    elif synoptic == "LOW_PRESSURE_SYSTEM":
        w[:, idx["MONSOON_DEPRESSION"]] *= 4.0
        w[:, idx["BREAK_MONSOON"]] *= 0.3

    w = np.clip(w, 1e-4, None)
    return w / w.sum(axis=1, keepdims=True)


def _sample_rows(rng: np.random.Generator, regimes: np.ndarray, d: pd.DataFrame) -> pd.DataFrame:
    """Draw features, observed rainfall and the raw NWP forecast for one day."""
    n = len(d)
    elev = d["elevation"].to_numpy(float)
    coast = d["distance_from_coast"].to_numpy(float)
    coastal_prox = np.exp(-coast / 60.0)
    orographic_gain = 1.0 + np.clip(elev, 0, 2600) / 1150.0

    rh = np.zeros(n); temp = np.zeros(n); pres = np.zeros(n)
    ws = np.zeros(n); wd = np.zeros(n); obs = np.zeros(n); raw = np.zeros(n)

    for regime in np.unique(regimes):
        m = regimes == regime
        k = int(m.sum())
        fs = REGIME_FEATURE_STATS[regime]
        rs = REGIME_RAIN_STATS[regime]
        es = REGIME_NWP_ERROR[regime]

        rh[m] = np.clip(rng.normal(fs["rh"][0], fs["rh"][1], k), 25, 100)
        # Lapse-rate style cooling with elevation (~6 K/km).
        temp[m] = rng.normal(fs["t"][0], fs["t"][1], k) - 0.0060 * elev[m]
        # Station pressure falls with height (~0.11 hPa/m near the surface).
        pres[m] = rng.normal(fs["p"][0], fs["p"][1], k) - 0.110 * elev[m]
        ws[m] = np.clip(rng.normal(fs["ws"][0], fs["ws"][1], k), 0.3, None)
        wd[m] = rng.normal(fs["wd"][0], fs["wd"][1], k) % 360.0

        # ---- "observed" rainfall -------------------------------------
        mean_mm = rs["base"]
        if regime in ("ACTIVE_MONSOON", "COASTAL_RAINFALL", "OROGRAPHIC_RAINFALL",
                      "MONSOON_DEPRESSION"):
            mean_mm = mean_mm * orographic_gain[m] * (1.0 + 0.55 * coastal_prox[m])
        elif regime == "WESTERN_DISTURBANCE":
            mean_mm = mean_mm * (1.0 + 0.45 * np.clip(elev[m], 0, 3000) / 1500.0)
        else:
            mean_mm = mean_mm * (1.0 + 0.10 * coastal_prox[m])
        mean_mm = np.asarray(mean_mm, dtype=float) * (0.65 + 0.7 * (rh[m] / 90.0) ** 2)

        shape = rs["shape"]
        rain = rng.gamma(shape, np.maximum(mean_mm, 0.2) / shape)
        rain = np.where(rng.random(k) < rs["dry_p"], 0.0, rain)
        obs[m] = np.clip(rain, 0, 700)

        # ---- raw NWP forecast (error model) --------------------------
        # Systematic bias grows with terrain height for the orographic and
        # coastal regimes: this is the signal the correction models learn.
        mult = es["mult"] * (1.0 - 0.10 * np.clip(elev[m], 0, 2500) / 2500.0)
        noise = rng.lognormal(0.0, es["sigma"], k)
        raw[m] = np.clip(
            obs[m] * mult * noise + es["add"] + rng.normal(0, es["jitter"], k),
            0, None,
        )

    return pd.DataFrame({
        "district": d["district"].to_numpy(),
        "state": d["state"].to_numpy(),
        "latitude": d["latitude"].to_numpy(float),
        "longitude": d["longitude"].to_numpy(float),
        "elevation": elev,
        "distance_from_coast": coast,
        "regime": regimes,
        "humidity": np.round(rh, 1),
        "temperature": np.round(temp, 1),
        "pressure": np.round(pres, 1),
        "wind_speed": np.round(ws, 1),
        "wind_direction": np.round(wd, 1),
        "raw_nwp_mm": np.round(raw, 1),
        "observed_rainfall_mm": np.round(obs, 1),
    })


def generate_dataset(n_days: int = 540,
                     start_date: Optional[dt.date] = None,
                     seed: int = RANDOM_SEED,
                     districts: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """Generate a synthetic district x day rainfall/NWP dataset.

    ``n_days`` days are sampled from a date range that deliberately spans
    monsoon and non-monsoon months so every regime is represented.
    """
    rng = np.random.default_rng(seed)
    d = districts if districts is not None else load_districts()
    start = start_date or dt.date(2021, 4, 1)

    frames = []
    synoptic = "QUIET"
    for i in range(n_days):
        date = start + dt.timedelta(days=i)
        # Synoptic states persist for a few days (Markov-style persistence).
        if rng.random() < 0.28:
            synoptic = str(rng.choice(SYNOPTIC_STATES, p=[0.34, 0.30, 0.16, 0.20]))
        weights = _regime_weights(d, date.month, synoptic)
        u = rng.random((len(d), 1))
        picks = (weights.cumsum(axis=1) < u).sum(axis=1).clip(0, len(REGIMES) - 1)
        regimes = np.array([REGIMES[p] for p in picks])

        day = _sample_rows(rng, regimes, d)
        day.insert(0, "date", date.isoformat())
        day["month"] = date.month
        day["day_of_year"] = date.timetuple().tm_yday
        day["synoptic_state"] = synoptic
        frames.append(day)

    out = pd.concat(frames, ignore_index=True)
    out["data_source"] = "SYNTHETIC_DEMO"
    return out


def generate_forecast_snapshot(for_date: Optional[dt.date] = None,
                               seed: Optional[int] = None,
                               districts: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """One synthetic 'today' forecast cycle: one row per district.

    The seed is derived from the date so the same day always produces the same
    demo forecast (stable screenshots, reproducible demos).
    """
    day = for_date or dt.date.today()
    if seed is None:
        seed = int(day.strftime("%Y%m%d")) % (2 ** 31)
    df = generate_dataset(n_days=1, start_date=day, seed=seed, districts=districts)
    # The "truth" column is kept but renamed: in a live system it would only
    # become available after the fact, when observations arrive.
    return df.rename(columns={"regime": "true_regime_synthetic"})
