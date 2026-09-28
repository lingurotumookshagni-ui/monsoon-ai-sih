# Data folder

## districts.csv

District metadata used everywhere in the project: 76 districts across Kerala, Tamil Nadu,
Karnataka, Maharashtra, Odisha, West Bengal, Assam, Andhra Pradesh, Telangana, Gujarat,
Rajasthan, Uttarakhand and Himachal Pradesh.

| Column | Meaning |
|---|---|
| `district` | District name |
| `state` | State name |
| `latitude`, `longitude` | Approximate district location (degrees) |
| `elevation` | Approximate elevation in metres |
| `distance_from_coast` | Approximate distance to the nearest coastline in kilometres |

Geographic values are **approximate**, included so the prototype has a plausible spatial
structure (coastal belt, Ghats, Himalayan foothills, interior plains). They are not survey data.
Replace this file with your own district or grid master list, or with centroids derived from a
district shapefile, and the rest of the project picks it up with no code changes.

## demo_rainfall.csv

**Synthetic. Created by the project, not measured anywhere.** Generated on first run of
`python train_models.py`, or directly with `python generate_demo_data.py`. Default size is
76 districts x 540 days, roughly 41,000 rows.

| Column | Meaning |
|---|---|
| `date` | Forecast/observation day |
| `district`, `state`, `latitude`, `longitude`, `elevation`, `distance_from_coast` | From `districts.csv` |
| `regime` | Synthetic regime label from the generator's own sampling process |
| `humidity`, `temperature`, `pressure`, `wind_speed`, `wind_direction` | Synthetic meteorological features |
| `raw_nwp_mm` | Synthetic "raw NWP" 24 h rainfall forecast |
| `observed_rainfall_mm` | Synthetic "observed" 24 h rainfall |
| `month`, `day_of_year` | Calendar fields |
| `synoptic_state` | The daily national state that shaped regime probabilities |
| `data_source` | Always `SYNTHETIC_DEMO` |

How it is built, and why each step is there, is documented at the top of
`backend/app/ml/synthetic.py`. In short: a persistent daily synoptic state shifts regime
probabilities nationally, geography and season weight them per district, features are drawn from
regime-conditional distributions, rainfall is drawn from a gamma distribution with orographic and
coastal enhancement, and the raw forecast is produced from the observation by a regime-dependent
error model (models under-forecast orographic and coastal heavy rain, displace depression
rainfall, over-forecast drizzle in break spells).

The regime labels here are **not** official meteorological regime classifications.

## Bringing in real data

See the section "Replacing demo data with real data" in the project README. Everything routes
through `backend/app/services/datasets.py`, which has three loader functions to swap.
