"""Central configuration for MonsoonAI.

Everything that a future operational deployment would want to change
(paths, rainfall thresholds, regime list, model filenames) lives here so
that no thresholds are hard-coded deep inside the ML or API code.
"""
from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------- paths
# backend/app/config.py -> backend/app -> backend -> project root
BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent

DATA_DIR = Path(os.getenv("MONSOONAI_DATA_DIR", PROJECT_ROOT / "data"))
MODELS_DIR = Path(os.getenv("MONSOONAI_MODELS_DIR", BACKEND_DIR / "models"))
OUTPUTS_DIR = Path(os.getenv("MONSOONAI_OUTPUTS_DIR", BACKEND_DIR / "outputs"))

DISTRICTS_CSV = DATA_DIR / "districts.csv"
DEMO_RAINFALL_CSV = DATA_DIR / "demo_rainfall.csv"

TRAIN_CSV = OUTPUTS_DIR / "train_dataset.csv"
EVAL_CSV = OUTPUTS_DIR / "eval_dataset.csv"
METRICS_JSON = OUTPUTS_DIR / "training_metrics.json"
VERIFICATION_JSON = OUTPUTS_DIR / "verification_report.json"

for _d in (DATA_DIR, MODELS_DIR, OUTPUTS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------- regimes
# Prototype regime taxonomy. These are *project-defined* regime classes
# inspired by the meteorology of the Indian monsoon. They are NOT official
# IMD regime definitions and must be re-defined with domain experts before
# any operational use.
REGIMES = [
    "ACTIVE_MONSOON",
    "BREAK_MONSOON",
    "MONSOON_DEPRESSION",
    "COASTAL_RAINFALL",
    "OROGRAPHIC_RAINFALL",
    "WESTERN_DISTURBANCE",
    "NORMAL_MONSOON",
]

REGIME_LABELS = {
    "ACTIVE_MONSOON": "Active monsoon",
    "BREAK_MONSOON": "Break monsoon",
    "MONSOON_DEPRESSION": "Monsoon low / depression",
    "COASTAL_RAINFALL": "Coastal rainfall",
    "OROGRAPHIC_RAINFALL": "Orographic rainfall",
    "WESTERN_DISTURBANCE": "Western disturbance",
    "NORMAL_MONSOON": "Normal monsoon",
}

REGIME_DESCRIPTIONS = {
    "ACTIVE_MONSOON": "Strong, well-organised monsoon flow with widespread rain over "
                      "central and peninsular India.",
    "BREAK_MONSOON": "Weak monsoon flow, subsident dry spell with suppressed rainfall "
                     "over the plains.",
    "MONSOON_DEPRESSION": "Low-pressure system or depression, typically Bay of Bengal "
                          "origin, producing very heavy localised rain.",
    "COASTAL_RAINFALL": "Onshore-flow rainfall concentrated along the west/east coastal belt.",
    "OROGRAPHIC_RAINFALL": "Terrain-forced uplift over the Ghats and Himalayan foothills; "
                           "NWP models often under-forecast the peaks.",
    "WESTERN_DISTURBANCE": "Extratropical system affecting north-west India and the "
                           "western Himalaya, mainly outside the monsoon season.",
    "NORMAL_MONSOON": "Climatologically ordinary monsoon conditions with no dominant "
                      "forcing.",
}

# filename used for the per-regime correction model
REGIME_MODEL_FILES = {
    "ACTIVE_MONSOON": "active_monsoon_model.joblib",
    "BREAK_MONSOON": "break_monsoon_model.joblib",
    "MONSOON_DEPRESSION": "depression_model.joblib",
    "COASTAL_RAINFALL": "coastal_model.joblib",
    "OROGRAPHIC_RAINFALL": "orographic_model.joblib",
    "WESTERN_DISTURBANCE": "western_disturbance_model.joblib",
    "NORMAL_MONSOON": "normal_model.joblib",
}

REGIME_CLASSIFIER_FILE = "regime_classifier.joblib"
GLOBAL_CORRECTION_FILE = "global_correction_model.joblib"
HEAVY_PROB_FILE = "heavy_rain_probability_model.joblib"
VERY_HEAVY_PROB_FILE = "very_heavy_rain_probability_model.joblib"

# ------------------------------------------------------- rainfall categories
# Configurable 24-hour accumulation thresholds (mm). These follow the widely
# published operational-style Indian rainfall classes, but the exact operational
# definitions should be verified against the relevant official standard before
# operational deployment.
RAINFALL_THRESHOLDS = {
    "LIGHT_MAX": 15.0,
    "MODERATE_MAX": 64.4,
    "HEAVY_MIN": 64.5,
    "HEAVY_MAX": 115.5,
    "VERY_HEAVY_MIN": 115.6,
    "VERY_HEAVY_MAX": 204.4,
    "EXTREMELY_HEAVY_MIN": 204.5,
}

# Public-facing "condition" scale used by the district lookup screens.
# It is derived from RAINFALL_THRESHOLDS above (no new science): the operational
# LIGHT class is split at 5 mm into LOW and NORMAL so that a citizen asking
# "what is the condition in my district?" gets a meaningful answer instead of
# everything below 15 mm looking identical. Each entry is (condition, lower bound mm).
PUBLIC_CONDITIONS = [
    ("VERY_HEAVY", RAINFALL_THRESHOLDS["VERY_HEAVY_MIN"]),
    ("HEAVY", RAINFALL_THRESHOLDS["HEAVY_MIN"]),
    ("MODERATE", RAINFALL_THRESHOLDS["LIGHT_MAX"]),
    ("NORMAL", 5.0),
    ("LOW", 0.0),
]

# Thresholds used for categorical (event) verification, in mm.
VERIFICATION_THRESHOLDS = [64.5, 115.6, 204.5]

# Prototype UI risk bands for heavy-rainfall probability (interpretation only).
RISK_BANDS = [
    ("VERY_HIGH", 0.70),
    ("HIGH", 0.45),
    ("MODERATE", 0.20),
    ("LOW", 0.0),
]

# ---------------------------------------------------------------- live data
# Open-Meteo (https://open-meteo.com) is a free, no-API-key numerical weather
# prediction service. It is used here because its hourly variable set is an
# exact match for the features RAW_INPUT_COLUMNS in app/ml/features.py needs
# (precipitation, humidity, temperature, pressure, wind speed and direction),
# so the trained models can run on live input without retraining or dropping
# a feature. Geography (elevation, distance_from_coast) is NOT requested from
# the weather API: it does not change day to day, a weather forecast API has
# no reason to serve it, and the project already has documented per-district
# values in data/districts.csv. Those are reused for live requests exactly as
# for demo ones - this is a deliberate, documented fallback, not a silently
# invented value.
LIVE_PROVIDER = "Open-Meteo"
LIVE_API_BASE_URL = "https://api.open-meteo.com/v1/forecast"
# Open-Meteo requires no API key for this endpoint. If a future provider does,
# its key belongs in an environment variable read only by the backend (see
# LIVE_PROVIDER_API_KEY below) and must never be sent to or read by the frontend.
LIVE_PROVIDER_API_KEY = os.getenv("LIVE_PROVIDER_API_KEY", "")
LIVE_HOURLY_VARIABLES = [
    "precipitation",
    "relative_humidity_2m",
    "temperature_2m",
    "surface_pressure",
    "wind_speed_10m",
    "wind_direction_10m",
]
# The "raw forecast" the models were trained on is a 24 h accumulation, so a
# live raw_nwp_mm is built by summing this many hourly precipitation values
# starting at the nearest forecast hour; the other variables are averaged
# over the same window. This is stated on every live response.
LIVE_WINDOW_HOURS = 24
LIVE_FORECAST_DAYS = 2          # ask the API for enough hours to cover the window
LIVE_REQUEST_TIMEOUT_SECONDS = 10
LIVE_BATCH_SIZE = 40            # districts per outbound request, keeps URLs short
LIVE_CACHE_TTL_SECONDS = 600    # 10 minutes: short enough to stay current,
                                 # long enough to avoid hammering a free public API
LIVE_STATUS_PING_LAT = 28.6139  # Delhi - used only for the lightweight /api/live/status check
LIVE_STATUS_PING_LON = 77.2090

# ---------------------------------------------------------------- misc
MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB upload cap
MAX_UPLOAD_ROWS = 20000
RANDOM_SEED = 42
DEMO_MODE_BANNER = "DEMO MODE - Synthetic/Example Weather Data"
