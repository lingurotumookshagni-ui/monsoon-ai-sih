"""CSV upload validation and processing.

Security posture for the prototype: the file is parsed as text only, size and
row count are capped, uploaded content is never written to disk or executed,
and no dynamic evaluation is used anywhere. Validation errors are returned as
explicit field-level messages; internal exceptions are never leaked.
"""
from __future__ import annotations

import io
from typing import Dict, List, Tuple

import pandas as pd

from ..config import MAX_UPLOAD_ROWS
from ..ml.registry import get_engine

# Minimum columns needed to post-process a forecast.
REQUIRED_COLUMNS = ["district", "latitude", "longitude", "raw_nwp_mm"]

# Used when present; filled with defaults when absent.
OPTIONAL_COLUMNS = [
    "state", "observed_rainfall_mm", "humidity", "pressure", "temperature",
    "wind_speed", "wind_direction", "elevation", "distance_from_coast",
    "month", "day_of_year", "date",
]

NUMERIC_COLUMNS = [
    "latitude", "longitude", "raw_nwp_mm", "observed_rainfall_mm", "humidity",
    "pressure", "temperature", "wind_speed", "wind_direction", "elevation",
    "distance_from_coast", "month", "day_of_year",
]

RANGES = {
    "latitude": (-90.0, 90.0),
    "longitude": (-180.0, 180.0),
    "raw_nwp_mm": (0.0, 2000.0),
    "observed_rainfall_mm": (0.0, 2000.0),
    "humidity": (0.0, 100.0),
    "pressure": (500.0, 1100.0),
    "temperature": (-60.0, 60.0),
    "wind_speed": (0.0, 120.0),
    "wind_direction": (0.0, 360.0),
    "elevation": (-500.0, 9000.0),
    "distance_from_coast": (0.0, 3000.0),
    "month": (1, 12),
    "day_of_year": (1, 366),
}


class UploadValidationError(Exception):
    """Raised with a list of human-readable problems found in the CSV."""

    def __init__(self, errors: List[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


def parse_and_validate(raw_bytes: bytes) -> Tuple[pd.DataFrame, Dict]:
    """Parse CSV bytes into a validated DataFrame plus a validation summary."""
    errors: List[str] = []
    warnings: List[str] = []

    if not raw_bytes:
        raise UploadValidationError(["The uploaded file is empty."])

    try:
        text = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise UploadValidationError(
            ["The file is not valid UTF-8 text. Save it as a UTF-8 CSV and try again."])

    try:
        df = pd.read_csv(io.StringIO(text))
    except Exception:
        raise UploadValidationError(
            ["The file could not be parsed as CSV. Check the delimiter and header row."])

    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]

    if df.empty:
        raise UploadValidationError(["The CSV has a header but no data rows."])
    if len(df) > MAX_UPLOAD_ROWS:
        raise UploadValidationError(
            [f"The CSV has {len(df)} rows; the limit is {MAX_UPLOAD_ROWS}."])

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        errors.append("Missing required column(s): " + ", ".join(missing)
                      + ". Required columns are: " + ", ".join(REQUIRED_COLUMNS) + ".")
    if errors:
        raise UploadValidationError(errors)

    for col in NUMERIC_COLUMNS:
        if col in df.columns:
            before = df[col].notna().sum()
            df[col] = pd.to_numeric(df[col], errors="coerce")
            bad = int(before - df[col].notna().sum())
            if bad:
                warnings.append(f"{bad} non-numeric value(s) in '{col}' were treated as missing.")

    n_before = len(df)
    df = df.dropna(subset=["district", "latitude", "longitude", "raw_nwp_mm"])
    dropped = n_before - len(df)
    if dropped:
        warnings.append(f"{dropped} row(s) dropped for missing required values.")
    if df.empty:
        raise UploadValidationError(
            ["No usable rows remain after validation: every row was missing a "
             "required value (district, latitude, longitude, raw_nwp_mm)."])

    for col, (lo, hi) in RANGES.items():
        if col in df.columns:
            out_of_range = int(((df[col] < lo) | (df[col] > hi)).sum())
            if out_of_range:
                warnings.append(
                    f"{out_of_range} value(s) in '{col}' were outside "
                    f"[{lo}, {hi}] and were clipped.")
                df[col] = df[col].clip(lo, hi)

    if "state" not in df.columns:
        df["state"] = "UNKNOWN"
        warnings.append("No 'state' column found; state set to UNKNOWN.")
    if "month" not in df.columns and "date" in df.columns:
        parsed = pd.to_datetime(df["date"], errors="coerce")
        df["month"] = parsed.dt.month
        df["day_of_year"] = parsed.dt.dayofyear
        warnings.append("'month' derived from the 'date' column.")

    missing_optional = [c for c in OPTIONAL_COLUMNS if c not in df.columns]
    if missing_optional:
        warnings.append(
            "Optional column(s) not provided, climatological defaults used: "
            + ", ".join(missing_optional) + ".")

    summary = {
        "rows_received": int(n_before),
        "rows_accepted": int(len(df)),
        "columns_detected": list(df.columns),
        "has_observations": bool("observed_rainfall_mm" in df.columns
                                 and df["observed_rainfall_mm"].notna().any()),
        "warnings": warnings,
    }
    return df.reset_index(drop=True), summary


def process_upload(df: pd.DataFrame) -> pd.DataFrame:
    """Run the regime + correction + probability pipeline on uploaded rows."""
    engine = get_engine()
    processed = engine.process(df)
    if "observed_rainfall_mm" in df.columns:
        processed["observed_rainfall_mm"] = pd.to_numeric(
            df["observed_rainfall_mm"], errors="coerce").to_numpy(float)
    return processed
