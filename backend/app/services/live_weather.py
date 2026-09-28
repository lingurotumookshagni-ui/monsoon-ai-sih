"""Live weather data provider.

Fetches a real numerical weather forecast from Open-Meteo
(https://open-meteo.com, no API key required) and converts it into exactly
the feature format the trained MonsoonAI models expect
(``app/ml/features.py:RAW_INPUT_COLUMNS``), so the existing regime classifier
and regime-specific correction models run unmodified on live input.

FEATURE MATCH
-------------
Open-Meteo's hourly variables map onto the trained model's inputs like this:

    model feature          Open-Meteo hourly variable
    ------------------      ---------------------------
    raw_nwp_mm          <-  precipitation        (summed over the window)
    humidity            <-  relative_humidity_2m (averaged over the window)
    temperature         <-  temperature_2m       (averaged over the window)
    pressure            <-  surface_pressure     (averaged over the window)
    wind_speed          <-  wind_speed_10m       (averaged over the window)
    wind_direction      <-  wind_direction_10m   (circular-averaged)
    latitude, longitude <-  the requested coordinate (echoed back by the API)

Two model features are geographic, not meteorological, so they are correctly
NOT requested from a weather forecast API:

    elevation            <-  data/districts.csv (static, already documented)
    distance_from_coast  <-  data/districts.csv (static, already documented)

``month`` and ``day_of_year`` are derived from the forecast reference time.
Every trained feature is therefore covered - there is no missing-feature
fallback to document for this provider.

ISOLATION
---------
Nothing outside this module knows the provider is Open-Meteo. Every function
below returns provider-agnostic dictionaries/DataFrames; the routes and the
ML registry never see a provider-specific field name. Adding a second
provider means writing another module with the same three entry points
(`fetch_batch`, `fetch_one`, `ping`) and switching what `get_provider()` in
this file returns - nothing else in the project changes.

RELIABILITY
-----------
- Every outbound call has a hard timeout (LIVE_REQUEST_TIMEOUT_SECONDS).
- Failures raise `LiveDataError` with a human-readable reason; callers must
  surface that reason rather than substituting synthetic data.
- Successful responses are cached in memory for LIVE_CACHE_TTL_SECONDS so a
  dashboard refresh does not hammer a free public API. Cache is per-process,
  not persisted - no database, no file writes.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from ..config import (
    LIVE_API_BASE_URL,
    LIVE_BATCH_SIZE,
    LIVE_CACHE_TTL_SECONDS,
    LIVE_FORECAST_DAYS,
    LIVE_HOURLY_VARIABLES,
    LIVE_PROVIDER,
    LIVE_REQUEST_TIMEOUT_SECONDS,
    LIVE_STATUS_PING_LAT,
    LIVE_STATUS_PING_LON,
    LIVE_WINDOW_HOURS,
)


class LiveDataError(Exception):
    """Raised whenever live data cannot be obtained or trusted.

    Callers (the API routes) must turn this into an explicit "unavailable"
    response. It must never be caught and silently replaced with demo data.
    """


@dataclass
class LiveWeatherPoint:
    latitude: float
    longitude: float
    raw_nwp_mm: float
    humidity: float
    temperature: float
    pressure: float
    wind_speed: float
    wind_direction: float
    forecast_time: str          # ISO timestamp the accumulation window starts at
    window_hours: int
    provider_elevation_m: Optional[float]
    fetched_at: str             # ISO timestamp this value was retrieved


# ------------------------------------------------------------------ cache
# key -> (expires_at_epoch, LiveWeatherPoint)
_CACHE: Dict[str, tuple] = {}
_LAST_SUCCESS: Optional[str] = None
_LAST_ERROR: Optional[str] = None


def _cache_key(lat: float, lon: float) -> str:
    # Round to ~1 km so nearby requests share a cache entry without merging
    # genuinely different districts.
    return f"{round(lat, 2)}:{round(lon, 2)}"


def clear_cache() -> None:
    _CACHE.clear()


def last_success() -> Optional[str]:
    return _LAST_SUCCESS


def last_error() -> Optional[str]:
    return _LAST_ERROR


# -------------------------------------------------------------- HTTP call
def _http_get_json(url: str, timeout: float) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "MonsoonAI/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
    except urllib.error.HTTPError as exc:
        raise LiveDataError(
            f"{LIVE_PROVIDER} returned HTTP {exc.code} for this request."
        ) from exc
    except urllib.error.URLError as exc:
        raise LiveDataError(
            f"Could not reach {LIVE_PROVIDER} ({exc.reason}). Check the network "
            "connection or try again shortly."
        ) from exc
    except TimeoutError as exc:
        raise LiveDataError(
            f"{LIVE_PROVIDER} did not respond within {timeout:.0f} seconds."
        ) from exc

    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise LiveDataError(f"{LIVE_PROVIDER} returned a response that was not valid JSON.") from exc


def _circular_mean_deg(degrees: List[float]) -> float:
    """Average of wind directions, which are circular (0 deg == 360 deg)."""
    radians = np.deg2rad(np.asarray(degrees, dtype=float))
    return float(np.rad2deg(np.arctan2(np.mean(np.sin(radians)), np.mean(np.cos(radians)))) % 360.0)


def _window_slice(hourly: dict) -> Dict[str, List[float]]:
    """Pick the LIVE_WINDOW_HOURS block starting at the first future hour."""
    times = hourly.get("time") or []
    if not times:
        raise LiveDataError(f"{LIVE_PROVIDER} response had no hourly time series.")

    now = dt.datetime.utcnow()
    start_index = 0
    for i, t in enumerate(times):
        try:
            parsed = dt.datetime.fromisoformat(t)
        except ValueError:
            continue
        if parsed >= now:
            start_index = i
            break
    end_index = start_index + LIVE_WINDOW_HOURS
    if end_index > len(times):
        # Not enough forecast hours left in the response; use what is left
        # rather than silently wrapping into the past.
        end_index = len(times)
        start_index = max(0, end_index - LIVE_WINDOW_HOURS)

    window = {"time": times[start_index:end_index]}
    for var in LIVE_HOURLY_VARIABLES:
        series = hourly.get(var)
        if series is None:
            raise LiveDataError(
                f"{LIVE_PROVIDER} response did not include '{var}', which the "
                "trained model requires. No value was invented for it."
            )
        window[var] = series[start_index:end_index]
    return window


def _point_from_location(location: dict) -> LiveWeatherPoint:
    hourly = location.get("hourly")
    if not hourly:
        raise LiveDataError(f"{LIVE_PROVIDER} response had no hourly forecast block.")

    window = _window_slice(hourly)
    if not window["time"]:
        raise LiveDataError(f"{LIVE_PROVIDER} had no usable forecast hours left for this location.")

    precip = [v for v in window["precipitation"] if v is not None]
    rh = [v for v in window["relative_humidity_2m"] if v is not None]
    temp = [v for v in window["temperature_2m"] if v is not None]
    pres = [v for v in window["surface_pressure"] if v is not None]
    wind = [v for v in window["wind_speed_10m"] if v is not None]
    wdir = [v for v in window["wind_direction_10m"] if v is not None]

    if not precip or not rh or not temp or not pres or not wind or not wdir:
        raise LiveDataError(
            f"{LIVE_PROVIDER} returned incomplete data (missing values) for this "
            "location's forecast window."
        )

    now_iso = dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    return LiveWeatherPoint(
        latitude=float(location.get("latitude")),
        longitude=float(location.get("longitude")),
        raw_nwp_mm=round(float(sum(precip)), 2),
        humidity=round(float(np.mean(rh)), 1),
        temperature=round(float(np.mean(temp)), 1),
        pressure=round(float(np.mean(pres)), 1),
        wind_speed=round(float(np.mean(wind)), 1),
        wind_direction=round(_circular_mean_deg(wdir), 1),
        forecast_time=window["time"][0],
        window_hours=len(window["time"]),
        provider_elevation_m=(
            float(location["elevation"]) if location.get("elevation") is not None else None
        ),
        fetched_at=now_iso,
    )


def _build_url(lats: List[float], lons: List[float]) -> str:
    params = {
        "latitude": ",".join(f"{v:.4f}" for v in lats),
        "longitude": ",".join(f"{v:.4f}" for v in lons),
        "hourly": ",".join(LIVE_HOURLY_VARIABLES),
        "forecast_days": str(LIVE_FORECAST_DAYS),
        "timezone": "UTC",
    }
    return f"{LIVE_API_BASE_URL}?{urllib.parse.urlencode(params)}"


def _fetch_points(coords: List[tuple]) -> List[LiveWeatherPoint]:
    """Fetch a batch of (lat, lon) coordinates in as few HTTP calls as possible.

    Open-Meteo accepts comma-separated lists of coordinates in a single
    request and returns one forecast object per location (or a single object,
    not wrapped in a list, when exactly one coordinate is given).
    """
    global _LAST_SUCCESS, _LAST_ERROR
    points: List[LiveWeatherPoint] = []
    try:
        for i in range(0, len(coords), LIVE_BATCH_SIZE):
            chunk = coords[i:i + LIVE_BATCH_SIZE]
            lats = [c[0] for c in chunk]
            lons = [c[1] for c in chunk]
            url = _build_url(lats, lons)
            data = _http_get_json(url, timeout=LIVE_REQUEST_TIMEOUT_SECONDS)
            locations = data if isinstance(data, list) else [data]
            if len(locations) != len(chunk):
                raise LiveDataError(
                    f"{LIVE_PROVIDER} returned {len(locations)} results for "
                    f"{len(chunk)} requested coordinates."
                )
            points.extend(_point_from_location(loc) for loc in locations)
    except LiveDataError as exc:
        _LAST_ERROR = str(exc)
        raise
    _LAST_SUCCESS = dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    _LAST_ERROR = None
    return points


def fetch_batch(coords: List[tuple], use_cache: bool = True) -> Dict[tuple, LiveWeatherPoint]:
    """Fetch (or reuse a cached) live weather point for each (lat, lon) pair."""
    now = time.time()
    result: Dict[tuple, LiveWeatherPoint] = {}
    to_fetch: List[tuple] = []

    if use_cache:
        for coord in coords:
            cached = _CACHE.get(_cache_key(*coord))
            if cached and cached[0] > now:
                result[coord] = cached[1]
            else:
                to_fetch.append(coord)
    else:
        to_fetch = list(coords)

    if to_fetch:
        fetched = _fetch_points(to_fetch)
        for coord, point in zip(to_fetch, fetched):
            _CACHE[_cache_key(*coord)] = (now + LIVE_CACHE_TTL_SECONDS, point)
            result[coord] = point

    return result


def fetch_one(lat: float, lon: float, use_cache: bool = True) -> LiveWeatherPoint:
    return fetch_batch([(lat, lon)], use_cache=use_cache)[(lat, lon)]


def ping() -> LiveWeatherPoint:
    """Lightweight reachability check used by GET /api/live/status."""
    return fetch_one(LIVE_STATUS_PING_LAT, LIVE_STATUS_PING_LON, use_cache=True)


# ------------------------------------------------------ feature assembly
def build_feature_frame(districts: pd.DataFrame, refresh: bool = False) -> pd.DataFrame:
    """Turn live weather points into a feature DataFrame the ML engine accepts.

    Columns match RAW_INPUT_COLUMNS in app/ml/features.py exactly. Raises
    LiveDataError (propagated from fetch_batch) if the provider cannot be
    reached - the caller must not fall back to synthetic values.
    """
    coords = list(zip(districts["latitude"].astype(float), districts["longitude"].astype(float)))
    points = fetch_batch(coords, use_cache=not refresh)

    now = dt.datetime.utcnow()
    rows = []
    for _, district in districts.iterrows():
        coord = (float(district["latitude"]), float(district["longitude"]))
        point = points[coord]
        forecast_dt = _safe_parse(point.forecast_time) or now
        rows.append({
            "district": district["district"],
            "state": district["state"],
            "latitude": district["latitude"],
            "longitude": district["longitude"],
            "elevation": district["elevation"],
            "distance_from_coast": district["distance_from_coast"],
            "raw_nwp_mm": point.raw_nwp_mm,
            "humidity": point.humidity,
            "temperature": point.temperature,
            "pressure": point.pressure,
            "wind_speed": point.wind_speed,
            "wind_direction": point.wind_direction,
            "month": forecast_dt.month,
            "day_of_year": forecast_dt.timetuple().tm_yday,
            "forecast_time": point.forecast_time,
            "fetched_at": point.fetched_at,
            "window_hours": point.window_hours,
            "provider_elevation_m": point.provider_elevation_m,
            "data_source": LIVE_PROVIDER,
        })
    return pd.DataFrame(rows)


def _safe_parse(value: str) -> Optional[dt.datetime]:
    try:
        return dt.datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
