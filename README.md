# MonsoonAI

**Regime-Aware AI Post-Processing of Monsoon Rainfall Forecasts**

A self-contained prototype that classifies the prevailing weather regime over each Indian district, applies a regime-specific machine-learning correction to a raw NWP rainfall forecast, estimates heavy-rainfall probability, and verifies the corrected forecast against the raw one with standard meteorological scores.

> **LIVE by default.** The dashboard fetches a real current forecast from Open-Meteo (no API key required) and runs it through the trained regime classifier and correction models. A **Demo / Test mode** with clearly labelled synthetic data is kept for offline development and testing - see section 2c. No database, paid service or cloud account is needed to run anything here.

---

## 1. Problem statement

Rainfall forecast errors over India vary with the weather situation. A model may badly under-forecast orographic rain over the Western Ghats, displace the rainfall core of a Bay of Bengal depression, and simultaneously over-forecast drizzle during a break spell. A single bias-correction curve fitted across all of these situations averages them together and corrects none of them well.

The task: build an AI/ML post-processing system that identifies the regime, corrects the forecast accordingly, pays particular attention to heavy and very heavy rainfall, produces a district-level product a non-specialist can read, and proves with verification metrics whether the correction actually helped.

## 2. Solution

Three models in sequence, per district, per forecast cycle:

```
 raw NWP rainfall + meteorological features + geography
                        |
        [1] regime classifier  (random forest, 7 classes)
                        |
        regime  ->  selects which correction model runs
                        |
        [2] regime-specific correction model  (gradient boosting on the residual)
                        |
        corrected rainfall (clipped at 0 mm)
                        |
        [3] heavy / very heavy probability  (calibrated classifiers)
                        |
      district product: regime, amount, correction, probability, category
                        |
        [4] verification: raw vs corrected vs observed
```

Splitting the correction by regime is the core idea: each regressor then only has to explain one coherent error pattern instead of an average of contradictory ones.

## 2a. Who the app is for

The dashboard serves two audiences from the same data, which is why the
navigation has a citizen half and a technical half:

- **Anyone who just wants to know about their own district.** The home screen
  offers three doors - *Check my district*, *Rainfall alerts*, *Detailed
  analysis*. "Check my district" answers one question in one screen: pick a
  district, press a button, get the expected rainfall, a condition band and a
  single plain sentence, in the language you chose. Every district is listed,
  including low and normal rainfall ones; alerts are a separate section, not a
  filter on the main product.
- **Judges, forecasters and reviewers.** Regimes, the post-processing workflow
  with a live run button, and the full verification table with RMSE, ETS, CSI,
  POD, FAR and FSS.

### Public condition bands

The citizen screens use a plain-language scale derived from the same
configured thresholds as the scientific categories (`PUBLIC_CONDITIONS` in
`backend/app/config.py`). No new science is introduced: the operational
"light" class is split at 5 mm so that a normal-rainfall district gets a
meaningful answer instead of everything under 15 mm looking identical.

| Condition | 24 h rainfall |
|---|---|
| Low | below 5 mm |
| Normal | 5 - 15 mm |
| Moderate | 15 - 64.4 mm |
| Heavy | 64.5 - 115.5 mm |
| Very heavy | 115.6 mm and above |

Severity is shown with an icon **and** text, never by colour alone.

## 2b. Languages

Seven languages, switchable from the header with no page reload: English,
മലയാളം, हिन्दी, தமிழ், తెలుగు, বাংলা, मराठी. Translations live in
`frontend/src/i18n/<code>.json` as flat dot-separated keys, with English as the
fallback for any key a language has not covered yet. Scientific abbreviations
(RMSE, ETS, CSI, POD, FAR, FSS) and all numeric values stay untranslated by
design. Current coverage: Malayalam and Hindi 97%, Tamil, Telugu, Bengali and
Marathi 92% - the uncovered keys are the plain-language metric descriptions on
the technical Metrics page, which fall back to English.

To add a language: copy `en.json`, translate the values, and add one entry to
`LANGUAGES` in `frontend/src/i18n/index.jsx`.

## 2c. LIVE mode

**LIVE is the default experience.** The dashboard now fetches a real weather
forecast, converts it into the trained models' feature format, and runs the
existing regime classifier and correction models on it - nothing about the
science changed, only where the input comes from.

### What "live" means here

"Live" means the raw NWP-style rainfall input comes from a real, current
numerical weather forecast (Open-Meteo), fetched fresh (subject to a short
cache) and post-processed by the same trained models used everywhere else in
this project. It does **not** mean the regime labels, the correction models,
or the verification scores are anything other than what they always were:
project-defined prototype regimes, models trained on synthetic data, and
skill scores computed on a synthetic hold-out period. Live only changes the
*input*, not the *models* or their *training data*.

### Data provider

**Open-Meteo** (<https://api.open-meteo.com>) — a free, public numerical
weather forecast API. **No API key is required**, so there is nothing to put
in an environment variable for this provider; the isolation point exists
anyway (see below) so a future provider that does need a key never touches
the frontend.

Feature match against the trained models (`app/ml/features.py:RAW_INPUT_COLUMNS`):

| Trained model feature | Live source |
|---|---|
| `raw_nwp_mm` | Open-Meteo `precipitation`, summed over the next 24 hourly values |
| `humidity` | Open-Meteo `relative_humidity_2m`, averaged over the same 24 h window |
| `temperature` | Open-Meteo `temperature_2m`, averaged over the window |
| `pressure` | Open-Meteo `surface_pressure`, averaged over the window |
| `wind_speed` | Open-Meteo `wind_speed_10m`, averaged over the window |
| `wind_direction` | Open-Meteo `wind_direction_10m`, circular-averaged over the window |
| `latitude`, `longitude` | The requested district coordinate, echoed back by the API |
| `elevation` | `data/districts.csv` (static geography - not requested from a weather API) |
| `distance_from_coast` | `data/districts.csv` (static geography - not requested from a weather API) |
| `month`, `day_of_year` | Derived from the forecast reference time |

**Every trained feature is covered.** No feature had to be dropped, and no
value was invented to paper over a gap - elevation and distance-from-coast
are correctly geographic, static inputs that a weather forecast API has no
reason to serve, and the project already had documented values for them.

### Backend service

`backend/app/services/live_weather.py` is the single seam to the outside
world. It is provider-isolated by design: every function it exposes
(`fetch_batch`, `fetch_one`, `ping`, `build_feature_frame`) returns
provider-agnostic data, so nothing else in the project - routes, the ML
registry, the frontend - knows the provider is Open-Meteo. Adding a second
provider means writing one more module with the same three entry points and
pointing the seam at it; no other file changes.

Reliability behaviour:
- Every outbound request has a **10 second timeout**.
- Requests are **batched** - up to 40 district coordinates in one HTTP call,
  so 76 districts costs 2 requests, not 76.
- Successful fetches are cached **in memory for 10 minutes** so repeated
  dashboard loads and the district-detail lookup do not hammer a free public
  API. The processed (post-model) result is cached separately for 2 minutes.
  There is no database and nothing is written to disk.
- Any failure (timeout, HTTP error, malformed response, a required variable
  missing from the response) raises `LiveDataError` with a specific reason.
  Every route that touches live data turns this into an **HTTP 503**, never
  a `200` with substituted or fabricated rows.

### API endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/live/status` | Provider reachability: `{mode, source, reachable, last_success, last_error, sample_forecast_time, sample_fetched_at}` |
| GET | `/api/live/districts` | The full district catalogue available in live mode - every district |
| GET | `/api/live/rainfall/{district}` | One district's live forecast, regime and AI-corrected rainfall |
| POST | `/api/live/refresh` | Clears the cache and re-fetches every district immediately |

Every other endpoint that used to be demo-only now also accepts
`?source=live` (the default when the parameter is omitted): `/api/forecast`,
`/api/overview`, `/api/districts/{name}`, `/api/heavy-rainfall`, `/api/process`,
`/api/verification`. `?source=demo` and `?source=uploaded` are unchanged and
still work exactly as before.

Example:

```bash
curl http://localhost:8000/api/live/rainfall/Kozhikode
```

```json
{
  "mode": "LIVE",
  "district": "Kozhikode",
  "state": "Kerala",
  "source": "Open-Meteo",
  "forecast_time": "2026-09-22T06:00:00",
  "last_updated": "2026-09-22T05:41:03Z",
  "window_hours": 24,
  "raw_rainfall_mm": 48.0,
  "post_processed_rainfall_mm": 61.62,
  "correction_mm": 13.62,
  "rainfall_probability": 0.41,
  "very_heavy_probability": 0.0014,
  "regime": "COASTAL_RAINFALL",
  "regime_confidence": 0.93,
  "category": "MODERATE",
  "condition": "MODERATE",
  "model_used": "regime_model:HistGradientBoostingRegressor",
  "observed_rainfall_mm": null,
  "note": "observed_rainfall_mm is null because the forecast window has not occurred yet."
}
```

### Model used for post-processing

Exactly the models `train_models.py` already produces - nothing new was
trained for live mode:

- **Regime**: `models/regime_classifier.joblib` (random forest)
- **Correction**: the matching `models/<regime>_model.joblib`
  (`HistGradientBoostingRegressor`, or `XGBRegressor` if xgboost happens to be
  installed), falling back to `models/global_correction_model.joblib` for a
  regime with too few training rows
- **Probability**: `models/heavy_rain_probability_model.joblib` and
  `models/very_heavy_rain_probability_model.joblib` (isotonic-calibrated)

If `backend/models/` is empty (fresh clone, before training), live mode still
answers - through the same documented heuristic fallback demo mode uses - and
`GET /api/health` / `GET /api/live/rainfall/{district}`'s `model_used` field
says so honestly.

### Scientific integrity in live mode

- **No observed rainfall exists for a live forecast** - the window it
  describes has not happened yet. `observed_rainfall_mm` is always `null` in
  live responses, and `/api/verification?source=live` returns
  `{"available": false, "reason": "..."}` rather than silently reusing the
  demo hold-out's scores under a "live" label.
- **Demo verification is unaffected** - `/api/verification?source=demo` still
  returns the real hold-out scores exactly as before; live and demo
  verification are never mixed.
- **Frontend never fabricates live data.** If the provider is unreachable,
  every live-mode page shows an explicit "LIVE DATA UNAVAILABLE" state with
  the real error message and a retry button, plus a manual "Try Demo / Test
  Mode" option. The browser-generated offline sample (`services/demoData.js`)
  is reachable only through Demo/Test mode when the backend itself cannot be
  reached at all, and is always labelled `DEMO DATA (offline fallback)` -
  never `LIVE`.

### Switching provider

1. Write a new module (e.g. `app/services/live_weather_ecmwf.py`) exposing
   the same `fetch_batch(coords)`, `fetch_one(lat, lon)`, `ping()` and
   `build_feature_frame(districts)` functions as `live_weather.py`.
   `build_feature_frame` must return the columns in
   `app/ml/features.py:RAW_INPUT_COLUMNS`.
2. If the provider needs an API key, read it with `os.getenv(...)` inside
   that module and add the variable name to `backend/.env.example` - it must
   never be read by or sent to the frontend.
3. Point the imports in `app/services/datasets.py` at the new module.
4. Update `LIVE_PROVIDER` in `app/config.py` so the name shown in the UI is
   correct.

### Environment variables

| Variable | Where | Required | Purpose |
|---|---|---|---|
| `VITE_API_URL` | `frontend/.env` | Yes | Backend URL the dashboard calls, e.g. `http://localhost:8000` |
| `LIVE_PROVIDER_API_KEY` | `backend/.env` (not committed) | No | Reserved for a future provider that needs a key. Open-Meteo needs none. Never read by the frontend. |

Copy `backend/.env.example` to `backend/.env` if you add a provider that
needs a key; `python-dotenv` is not required for Open-Meteo since it needs no
key, but if you add one, load it in `app/config.py` with
`os.getenv("LIVE_PROVIDER_API_KEY", "")` as already scaffolded there.

## 3. Architecture

```
monsoon-ai/
├── backend/
│   ├── app/
│   │   ├── main.py                 FastAPI app, CORS, error handling
│   │   ├── config.py               paths, regimes, thresholds, limits
│   │   ├── schemas.py              Pydantic request/response models
│   │   ├── routes/
│   │   │   ├── meta.py             /, /api/health, /api/districts, /api/regimes, /api/config, /api/model-metrics
│   │   │   ├── forecast.py         /api/forecast, /api/overview, /api/heavy-rainfall, /api/forecast/summary
│   │   │   ├── live.py             /api/live/status, /api/live/districts, /api/live/rainfall/{d}, /api/live/refresh
│   │   │   ├── predict.py          /api/predict-regime, /api/postprocess, /api/heavy-rainfall-probability
│   │   │   ├── verify.py           /api/verification
│   │   │   └── upload.py           /api/upload-data (POST/GET/DELETE) and /template
│   │   ├── ml/
│   │   │   ├── synthetic.py        synthetic demo data generator (documented)
│   │   │   ├── features.py         one shared feature builder for train + inference + live
│   │   │   ├── rules.py            deterministic heuristic fallback
│   │   │   ├── registry.py         model loading and vectorised inference
│   │   │   └── train.py            the training pipeline
│   │   ├── services/
│   │   │   ├── datasets.py         the data seam: districts, live/demo/uploaded dispatch, archive
│   │   │   ├── live_weather.py     Open-Meteo provider, isolated, cached, provider-agnostic
│   │   │   ├── verification.py     RMSE, MAE, POD, FAR, CSI, ETS, FSS
│   │   │   └── uploads.py          CSV parsing and validation
│   │   └── utils/categories.py     rainfall categories and risk bands
│   ├── tests/
│   │   ├── test_core.py            ML, metrics, data and validation tests (20)
│   │   ├── test_live.py            live provider, caching, outage handling (9)
│   │   └── test_api.py             endpoint tests via FastAPI TestClient (54)
│   ├── models/                     trained .joblib artefacts (created by training)
│   ├── outputs/                    datasets, metrics, verification report
│   ├── train_models.py
│   ├── generate_demo_data.py
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx                 shell, navigation, i18n, live/demo/uploaded state machine
│   │   ├── pages/                  Home, CheckDistrict, Alerts, Forecast (all districts),
│   │   │                           Regimes, PostProcessing, Verification, DataSource, About
│   │   ├── components/             map, table, KPI cards, district result/modal, language
│   │   │                           selector, live status badge, toasts, processing steps,
│   │   │                           upload panel, states
│   │   ├── charts/                 Recharts visualisations
│   │   ├── i18n/                   en, ml, hi, ta, te, bn, mr + provider with English fallback
│   │   ├── services/               API client, display constants, offline demo generator
│   │   └── styles/global.css       design tokens, dark/light, motion, responsive layout
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── data/
│   ├── districts.csv               76 districts, 13 states (approximate geography)
│   ├── demo_rainfall.csv           synthetic dataset (created by training/generation)
│   └── README.md
├── README.md
└── .gitignore
```

## 4. ML pipeline

`python train_models.py` runs six stages and prints metrics for each:

1. **Build the dataset.** Loads `data/demo_rainfall.csv`, generating it synthetically if absent (76 districts × 540 days ≈ 41,000 rows).
2. **Split by date.** The last 22% of *days* becomes the hold-out set. A random row split would leak the same synoptic day into training and evaluation and inflate every score.
3. **Train the regime classifier.** Random forest, balanced class weights, evaluated with accuracy, macro-F1 and a per-class report.
4. **Train the correction models.** One gradient-boosted regressor per regime plus a global fallback for regimes with fewer than 250 training rows.
5. **Train the probability models.** Two binary classifiers with isotonic calibration, scored with ROC-AUC and the Brier score.
6. **Evaluate and save.** The full live pipeline runs on the hold-out period; artefacts go to `models/`, datasets and reports to `outputs/`.

Typical output on the default synthetic dataset (your numbers will match if you keep the default seed):

```
Regime classifier:   accuracy 0.887   macro-F1 0.866
Correction (MAE raw -> corrected, hold-out):
  BREAK_MONSOON         4.76 ->  0.95   (80.1% better)
  OROGRAPHIC_RAINFALL  71.81 -> 43.65   (39.2% better)
  WESTERN_DISTURBANCE   3.54 ->  2.49   (29.7% better)
  COASTAL_RAINFALL     27.59 -> 23.62   (14.4% better)
  NORMAL_MONSOON        3.36 ->  2.96   (12.0% better)
  MONSOON_DEPRESSION   67.15 -> 65.03   ( 3.2% better)
  ACTIVE_MONSOON       20.17 -> 19.56   ( 3.1% better)
Heavy (>=64.5 mm):       ROC-AUC 0.991, Brier 0.035
Very heavy (>=115.6 mm): ROC-AUC 0.988, Brier 0.036
Verification at 64.5 mm:
  RMSE 44.53 -> 39.70  (10.9% lower)      MAE 19.31 -> 16.94  (12.2% lower)
  CSI  0.791 -> 0.842   POD 0.814 -> 0.929
  ETS  0.729 -> 0.785   FSS 0.918 -> 0.943
  FAR  0.033 -> 0.100   (worse)
```

That last line is worth saying out loud rather than hiding: the correction raises heavy rainfall amounts, so it catches far more real heavy-rain events (POD 0.81 → 0.93) at the cost of more false alarms (FAR 0.03 → 0.10). CSI and ETS, which account for both, still improve, so the trade is a net gain on this dataset — but whether that trade is acceptable is an operational decision, not a modelling one.

## 5. Weather regimes

| Regime | Meaning in this prototype |
|---|---|
| `ACTIVE_MONSOON` | Strong organised monsoon flow, widespread rain |
| `BREAK_MONSOON` | Weak flow, subsident dry spell, suppressed rainfall |
| `MONSOON_DEPRESSION` | Low-pressure system or depression, very heavy localised rain |
| `COASTAL_RAINFALL` | Onshore-flow rainfall along the coastal belt |
| `OROGRAPHIC_RAINFALL` | Terrain-forced uplift over the Ghats and Himalayan foothills |
| `WESTERN_DISTURBANCE` | Extratropical system over north-west India and the western Himalaya |
| `NORMAL_MONSOON` | Climatologically ordinary conditions, no dominant forcing |

Classifier features: raw NWP rainfall (and its log), humidity, temperature, pressure, wind speed, wind direction (as sine and cosine, since direction is circular), latitude, longitude, elevation (and its log), distance from coast, a coastal-proximity decay term, month, and day of year as sine and cosine.

**These regime classes are defined by this project.** In demo mode the labels come from the synthetic generator's own sampling process. They are not official meteorological regime classifications, and the classifier has not been validated against any expert-labelled regime archive. Replacing these definitions with expert ones is the first thing a real deployment would do.

## 6. Post-processing methodology

Each regime has its own regressor (`HistGradientBoostingRegressor`, or `XGBRegressor` automatically if xgboost happens to be installed) trained on the **residual**:

```
target  = observed_rainfall_mm - raw_nwp_mm
output  = max(0, raw_nwp_mm + predicted_residual)
```

Learning the residual rather than the absolute amount has two advantages. The model only has to explain forecast error, which is a smaller and better-behaved signal than rainfall itself, and it fails safe: a prediction of zero returns the raw forecast unchanged rather than an invented number. Rainfall is clipped at 0 mm, so a correction can never produce negative rain.

Regimes with fewer than 250 training rows fall back to a global correction model, and if `models/` is empty entirely, the API answers with a documented deterministic heuristic (`app/ml/rules.py`) and marks every response `method = "heuristic_fallback"` so a heuristic is never silently presented as a model output.

## 7. Heavy rainfall probability

Category thresholds for 24-hour accumulation, all configurable in `app/config.py`:

| Category | Range |
|---|---|
| Light | below 15 mm |
| Moderate | 15 – 64.4 mm |
| Heavy | 64.5 – 115.5 mm |
| Very heavy | 115.6 – 204.4 mm |
| Extremely heavy | 204.5 mm and above |

These follow widely published operational-style Indian rainfall classes. **Verify the exact operational definitions against the relevant official standard before any operational deployment.**

Two binary classifiers estimate P(rainfall ≥ 64.5 mm) and P(rainfall ≥ 115.6 mm), conditioned on the *corrected* amount plus all the regime features. Both are wrapped in `CalibratedClassifierCV` with isotonic regression: a random forest's vote fraction is not a probability, and the difference matters when the number will be read as a likelihood of heavy rain. A monotonicity guard enforces P(very heavy) ≤ P(heavy).

The dashboard's four risk bands (low / moderate / high / very high, cut at 20%, 45% and 70%) are a **prototype reading aid only**, not warning criteria.

## 8. Verification metrics

Implemented in `app/services/verification.py`, exposed at `GET /api/verification`:

- **Continuous:** RMSE, MAE, mean bias, correlation.
- **Categorical**, at each configurable threshold (default 64.5, 115.6, 204.5 mm), from the 2×2 contingency table of hits `h`, misses `m`, false alarms `f` and correct negatives `c`:
  - `POD = h / (h + m)`
  - `FAR = f / (h + f)`
  - `CSI = h / (h + m + f)`
  - `ETS = (h - h_random) / (h + m + f - h_random)`, where `h_random = (h + m)(h + f) / total`
  - frequency bias `= (h + f) / (h + m)`
- **FSS:** neighbourhood Fractions Skill Score, `FSS = 1 - MSE(Pf, Po) / (mean(Pf²) + mean(Po²))`.

Every score returns `null` instead of dividing by zero when it is genuinely undefined (for example POD when nothing was observed), and the dashboard renders that as `n/a`.

**FSS is a simplified prototype implementation.** The textbook score uses square neighbourhoods on a regular grid. The demo data is district-point based, so a district's "neighbourhood" is every district within 150 km great-circle distance, averaged over all forecast days. The formula is the standard one; only the neighbourhood definition differs. With a real gridded NWP field, replace `fractions_skill_score` with a grid-based neighbourhood computation and the score definition stays identical.

## 9. Tech stack

Backend: Python, FastAPI, Uvicorn, Pydantic, pandas, NumPy, scikit-learn, joblib. Optional: xgboost (used automatically if present, never required).
Frontend: React 18, Vite, Recharts, Leaflet via react-leaflet, plain `fetch`. No CSS framework, no router, no state library.
Storage: local files only — `data/`, `backend/models/`, `backend/outputs/`. **No database.**

## 10. Installation

Requires **Python 3.12** and Node.js 18+.

> **Python version matters.** Install with 3.12. On 3.13/3.14 several
> scientific wheels are not published yet, pip falls back to building pandas
> and numpy from source, and you get the
> `metadata-generation-failed` / Meson / `vswhere.exe` error that asks for
> Visual Studio Build Tools. Every pin in `requirements.txt` has a pre-built
> 3.12 wheel, so no compiler is needed.

### Backend setup

```bash
cd backend

# Windows
py -3.12 -m venv venv
venv\Scripts\activate

# macOS / Linux
python3.12 -m venv venv
source venv/bin/activate

python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Train the models

```bash
python train_models.py
```

Takes roughly one to two minutes and creates `data/demo_rainfall.csv`, all artefacts in `backend/models/`, and the datasets, metrics and verification report in `backend/outputs/`. Useful variants:

```bash
python train_models.py --days 900        # longer synthetic record
python train_models.py --rebuild-data    # regenerate the synthetic dataset first-p
python generate_demo_data.py --days 720  # generate data only, no training
```

### Start the API

```bash
uvicorn app.main:app --reload --port 8000
```

API root <http://localhost:8000>, interactive docs <http://localhost:8000/docs>.

The API also starts *before* training: it will answer using the documented heuristic fallback and say so in `/api/health`. Live mode additionally needs outbound internet access to `api.open-meteo.com`; Demo/Test mode and CSV upload do not need internet access at all.

### Frontend setup

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Dashboard at <http://localhost:5173>. The backend URL comes from `frontend/.env`:

```
VITE_API_URL=http://localhost:8000
```

Production build: `npm run build`, then `npm run preview`.

### Run the tests

```bash
cd backend
python -m pytest -q
```

## 11. Which terminal runs what

| Terminal | Directory | Command | Serves |
|---|---|---|---|
| 1 | `backend/` | `uvicorn app.main:app --reload --port 8000` | API at `http://localhost:8000` |
| 2 | `frontend/` | `npm run dev` | Dashboard at `http://localhost:5173` |

## 12. API reference

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | Service metadata and endpoint list |
| GET | `/api/health` | Status, which models are loaded, live-provider reachability |
| GET | `/api/config` | Thresholds, risk bands, disclaimer |
| GET | `/api/districts` | District catalogue |
| GET | `/api/districts/{name}` | One district: citizen view, regime, explanation key. `?source=live\|demo\|uploaded` |
| POST | `/api/process` | Run the pipeline now and report what each stage did. `?source=live\|demo\|uploaded` |
| GET | `/api/regimes` | Regime catalogue with per-regime statistics for the requested source |
| GET | `/api/forecast` | District forecasts. Filters: `state`, `district`, `regime`, `category`, `min_heavy_probability`, `min_rainfall`, `sort_by`, `limit`, `source` (default `live`), `date` (demo only) |
| GET | `/api/overview` | Everything the Overview/Home page needs in one call |
| GET | `/api/heavy-rainfall` | Probability-ranked watchlist |
| GET | `/api/verification` | Raw vs corrected vs observed report. `source=live` returns `{"available": false, "reason": ...}` since a live forecast has no observation yet |
| GET | `/api/model-metrics` | The full training report from the last run |
| POST | `/api/predict-regime` | Regime, confidence, probabilities |
| POST | `/api/postprocess` | Regime-aware bias correction for one point |
| POST | `/api/heavy-rainfall-probability` | P(heavy), P(very heavy), category, risk band |
| POST | `/api/upload-data` | Validate and process a CSV |
| GET/DELETE | `/api/upload-data` | Upload status / clear the uploaded set |
| GET | `/api/live/status` | Provider reachability, without a full district fetch |
| GET | `/api/live/districts` | The district catalogue available in live mode - every district |
| GET | `/api/live/rainfall/{district}` | One district's live forecast, regime and AI-corrected rainfall |
| POST | `/api/live/refresh` | Force a fresh fetch for every district, bypassing the cache |

See section 2c for the full LIVE mode reference, including the Open-Meteo feature mapping and outage behaviour.

Example:

```bash
curl -X POST http://localhost:8000/api/postprocess \
  -H "Content-Type: application/json" \
  -d '{"district":"Kasaragod","state":"Kerala","raw_nwp_mm":82,"humidity":88,
       "temperature":27.5,"pressure":1001,"wind_speed":9.5,"wind_direction":255,
       "latitude":12.5,"longitude":74.99,"elevation":20,"distance_from_coast":5,"month":7}'
```

```json
{
  "district": "Kasaragod",
  "regime": "COASTAL_RAINFALL",
  "raw_nwp_mm": 82.0,
  "corrected_rainfall_mm": 109.64,
  "correction_mm": 27.64,
  "confidence": 0.98,
  "category": "HEAVY",
  "heavy_probability": 0.978,
  "very_heavy_probability": 0.672,
  "method": "regime_model:HistGradientBoostingRegressor",
  "data_source": "SYNTHETIC_DEMO"
}
```

Only `raw_nwp_mm` is mandatory; anything omitted is filled with climatological defaults rather than rejected.
This endpoint takes hand-supplied features and is unaffected by `source` - to post-process a live
forecast for a district, use `GET /api/live/rainfall/{district}` or `GET /api/forecast?source=live` instead.

## 13. CSV upload format

Upload on the **Data source** page, or `POST /api/upload-data` with `multipart/form-data`.

Required columns: `district`, `latitude`, `longitude`, `raw_nwp_mm`.

Optional: `state`, `observed_rainfall_mm`, `humidity`, `pressure`, `temperature`, `wind_speed`, `wind_direction`, `elevation`, `distance_from_coast`, `month`, `day_of_year`, `date`.

```csv
district,state,latitude,longitude,raw_nwp_mm,observed_rainfall_mm,humidity,pressure,temperature,wind_speed,elevation,distance_from_coast,month
Kasaragod,Kerala,12.50,74.99,82,103,88,1001,27.5,9.5,20,5,7
Wayanad,Kerala,11.69,76.13,95,168,90,905,21.0,8.0,780,55,7
Pune,Maharashtra,18.52,73.86,12,4,62,1005,32.0,4.0,560,90,7
```

Validation returns field-level messages for missing columns, rejects files over 5 MB or 20,000 rows, coerces non-numeric values to missing, clips out-of-range values and reports every one of those actions as a warning. Include `observed_rainfall_mm` and your upload is verified too, with the same scores as the demo report.

Uploaded data is held **in the API process memory only** — nothing is written to disk, nothing is executed, and there is no database.

## 14. Switching between live, demo and uploaded data

Open **Data source** in the dashboard: three buttons, **Live mode** (default), **Demo / Test mode**,
and **Uploaded CSV** (enabled once a file has been processed). Every page - Home, Check your district,
Rainfall alerts, All districts, Regimes, Post-processing, Metrics - reads from whichever source is
selected there; there is no separate "live dashboard". Over the API, pass `?source=live`, `?source=demo`
or `?source=uploaded` to `/api/forecast`, `/api/overview`, `/api/districts/{name}`, `/api/process`,
`/api/heavy-rainfall` and `/api/verification` (omit the parameter for the default, `live`).

## 15. Replacing demo data with real data

Everything the system serves passes through `backend/app/services/datasets.py`. That file is the seam: three functions, and nothing else in the codebase needs to change.

| Function | Demo behaviour | Replace with |
|---|---|---|
| `load_districts()` | Reads `data/districts.csv` | Your district or grid master list, or centroids derived from a district shapefile |
| `load_forecast_cycle()` | Synthesises one forecast day | A reader for your NWP output (GRIB2/NetCDF via `xarray`/`cfgrib`), aggregated to district level |
| `load_verification_set()` | Reads the training hold-out CSV | Your archive of matched (forecast, observation) pairs |

To bring in real data:

1. **NWP forecasts.** Point `load_forecast_cycle()` at your model output. Provide the same columns the pipeline expects: `raw_nwp_mm`, `humidity`, `temperature`, `pressure`, `wind_speed`, `wind_direction`, plus district geography. Grid-based forecasts should be aggregated to districts (area mean, or maximum if you care more about peak rainfall than areal average).
2. **Rain gauge observations.** Supply as `observed_rainfall_mm` in the training table and the verification archive. Quality-control them first: gauge errors will be learned as forecast bias otherwise.
3. **Satellite or merged rainfall.** Use as the observation target where gauge density is thin, or as an extra predictor column — add it to `RAW_INPUT_COLUMNS` and the feature lists in `app/ml/features.py` and retrain.
4. **Regime information.** Replace the synthetic labels with expert or objectively defined regimes (for example from monsoon indices, circulation classification, or an operational regime archive) in the `regime` column of the training table, update `REGIMES` and `REGIME_MODEL_FILES` in `app/config.py`, and retrain.
5. Run `python train_models.py` against the real table and re-read the verification report before trusting anything.

No IMD or third-party API access is claimed, assumed or required anywhere in this repository. There are no credentials to configure because there are no external services.

## 16. SIH demo flow

About three and a half minutes, one connected story:

1. **Home (15 s).** Three cards, LIVE ● showing in the header. "Two audiences, one product: a citizen who wants their district, and a reviewer who wants the science - and everything you're about to see is a real, current forecast."
2. **Check my district (30 s).** Pick Malappuram, press *Check condition*. Read the big number, the condition band and the one-sentence explanation. Expand *Show technical details* - same record, raw live forecast, AI correction, calibrated probabilities, forecast time and last-updated timestamp.
3. **All districts (20 s).** "Every district is here, including low and normal rainfall, and it's all live right now." Tap a condition chip to filter, click any row to open its detail modal.
4. **Rainfall alerts (20 s).** "Only the districts that need attention - a separate section, not a filter that hides everyone else."
5. **Weather regimes (20 s).** "The correction isn't one model. The classifier picks the regime and that routes the district to a model trained only on that situation - orographic gets pushed up hard, break monsoon pulled down."
6. **Post-processing (30 s).** Press *Run post-processing*. The stages that appear are the backend's own report on the live fetch, with the real time each one took. Then the raw-vs-corrected chart, built from real values.
7. **Live refresh (10 s).** Press *↻ Refresh live data* in the header. "This clears the cache and pulls a fresh forecast from Open-Meteo right now." Point at the updated timestamp.
8. **Metrics (25 s).** Switch to Demo/Test mode first: "Live forecasts have no observation yet, so live verification honestly says 'not available' - here's what the same models scored on the training hold-out." RMSE down 11%, CSI/POD/ETS/FSS up, FAR up (explain the trade).
9. **Language (15 s).** Switch to മലയാളം or हिन्दी from the header. The whole interface, including the district explanation, changes with no reload.
10. **About (10 s).** "And here's what's live, what's synthetic, and what a real deployment would still need."

Judges usually ask: *is this actually live, or dressed-up demo data?* Turn off your internet connection
and press Refresh - the dashboard shows "LIVE DATA UNAVAILABLE" with the real error, not a silent
switch to fake numbers. *Why not one model?* Answer with the regime page — opposite-signed corrections
in the same cycle cannot be produced by a single fitted curve. *How do you know the models work?*
Answer with the temporal hold-out in Metrics: whole weather days withheld, not random rows.

## 17. What is genuinely implemented vs simulated

**Genuinely live:**
- The raw rainfall forecast, humidity, temperature, pressure, wind speed and wind direction for
  every district, fetched from Open-Meteo for the current forecast cycle
- The regime classification and AI correction run on that live input, through the same trained
  models used everywhere else - not a separate "live model"

**Genuinely implemented and running:**
- Random forest regime classifier, trained, saved, and serving live and demo predictions
- Seven regime-specific gradient-boosted correction models plus a global fallback
- Two isotonic-calibrated heavy-rainfall probability classifiers
- The live data service: batched requests, in-memory caching, timeouts, and honest HTTP 503s on
  provider outage - never a substituted value
- The full verification module: RMSE, MAE, bias, correlation, POD, FAR, CSI, ETS, FSS, contingency tables, at multiple thresholds, with divide-by-zero handling
- Temporal hold-out evaluation and the improvement percentages, all computed from data — no hard-coded figures anywhere
- 22 endpoints with Pydantic validation, CORS, size-limited and validated CSV upload, HTTP error codes, no stack traces exposed
- The complete dashboard: map, sortable tables, filters, charts, upload, dark and light views, loading and error states, live status indicator, offline fallback
- 83 tests across the ML core, the live pipeline and the API

**Simulated / demo (Demo / Test mode only):**
- All rainfall, observations and meteorological features (`app/ml/synthetic.py`)
- Regime *labels* in the demo dataset, which come from the generator's sampling process rather than meteorological analysis
- The NWP error model, which is a plausible construction, not a measured characterisation of any real model
- District geography, which is approximate (used in both live and demo mode - see section 2c)
- The offline browser fallback, which uses a heuristic correction rather than the trained models, and only appears when Demo/Test mode is selected and the backend itself is unreachable
- **Never labelled live**: demo data is always shown with a "DEMO MODE" or "DEMO DATA" chip, checked explicitly in the test suite (`test_demo_mode_never_labelled_live`)

## 18. Limitations

- Live mode improves the *input* to the models (a real forecast instead of a synthetic one), but the
  models themselves are still trained on synthetic data. A live-mode prediction is a real regime
  classification and a real learned correction applied to real weather, but its accuracy has not been
  verified against real observed rainfall - see the next point.
- There is no live verification: a live forecast's 24 h window has not occurred yet, so RMSE/CSI/POD/
  FAR/ETS/FSS cannot be computed for it. `/api/verification?source=live` says so explicitly rather than
  reusing the demo hold-out's numbers.
- Open-Meteo's own forecast skill is not evaluated here; this project post-processes whatever it returns.
- Skill scores shown in Demo/Test mode measure performance on synthetic data with a known error structure. They demonstrate that the method works on data of this shape; they say nothing about real forecast skill.
- The heavy-rainfall classifiers see in-sample corrected amounts during training, which slightly flatters their calibration. Cross-fitted corrections would fix it.
- FSS uses district neighbourhoods, not grid neighbourhoods.
- No lead-time dimension: the prototype post-processes a single accumulation window rather than a forecast sequence.
- No ensemble input, so the probabilities come from a classifier rather than from forecast spread.
- Uploaded data lives in process memory, so it is lost when the API restarts and is not shared between workers.
- CORS is fully open, which is fine locally and wrong in production.
- Translations are hand-written for the user-facing keys; Tamil, Telugu, Bengali and Marathi do not yet cover the plain-language metric descriptions, which fall back to English.
- The district lookup has no geolocation: the user picks their district from a list rather than being detected.
- There is no district boundary layer on the map; districts are plotted as points from their approximate centroids.
- The live cache is per-process and in memory: restarting the backend clears it, and it is not shared across multiple backend workers if you run more than one.
- `GET /api/live/status` pings a single fixed coordinate for a fast reachability check; it does not guarantee every district's data is already warm in the cache.

## 19. Future improvements

- Quantile regression or distributional output instead of a single corrected amount, giving a full predictive distribution rather than a point value plus two threshold probabilities
- Cross-fitted corrections before probability training
- Proper gridded FSS with multiple neighbourhood sizes and a skill-versus-scale curve
- Lead-time-aware models and an ensemble-aware version that post-processes spread as well as the mean
- Soft regime handling: weight the correction models by classifier probability instead of routing to the single most likely regime, which smooths the discontinuity at regime boundaries
- Reliability diagrams and sharpness for the probability product, alongside Brier score decomposition
- Persistent storage of forecast cycles and verification history so skill can be tracked over a season

## 20. Disclaimer

This prototype is intended for research and hackathon demonstration. Demo forecasts are synthetic and are not official weather forecasts. Real operational deployment requires validated NWP forecasts, quality-controlled observations, appropriate regime definitions, spatial/temporal validation, calibration, and collaboration with meteorological experts.
