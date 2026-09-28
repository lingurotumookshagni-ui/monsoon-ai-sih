"""Tests for LIVE mode: provider parsing, caching, the full model pipeline on
live-shaped input, and the /api/live/* and source=live routes.

No real network call is made. `app.services.live_weather._http_get_json` is
the single seam to the outside world, and every test monkeypatches exactly
that function - so these tests prove the parsing, feature-conversion and
model-integration logic without depending on Open-Meteo being reachable.
"""
from __future__ import annotations

import datetime as dt
import urllib.parse

import pytest

from app.config import REGIMES
from app.services import datasets, live_weather as lw
from app.services.live_weather import LiveDataError


def _make_location(lat: float, lon: float, base_precip: float = 2.0, hours: int = 48) -> dict:
    now = dt.datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    times = [(now + dt.timedelta(hours=h)).isoformat() for h in range(hours)]
    n = len(times)
    return {
        "latitude": lat,
        "longitude": lon,
        "elevation": 12.3,
        "hourly": {
            "time": times,
            "precipitation": [base_precip + (h % 5) * 0.4 for h in range(n)],
            "relative_humidity_2m": [80.0 + (h % 10) for h in range(n)],
            "temperature_2m": [26.0 + (h % 4) for h in range(n)],
            "surface_pressure": [1000.0 + (h % 3) for h in range(n)],
            "wind_speed_10m": [7.0 + (h % 6) * 0.3 for h in range(n)],
            "wind_direction_10m": [(200 + h * 3) % 360 for h in range(n)],
        },
    }


def _fake_transport(monkeypatch, precip_by_coord=None):
    """Install a fake HTTP layer that answers like Open-Meteo would."""
    def fake_get(url, timeout):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        lats = [float(x) for x in q["latitude"][0].split(",")]
        lons = [float(x) for x in q["longitude"][0].split(",")]
        locs = []
        for lat, lon in zip(lats, lons):
            base = (precip_by_coord or {}).get((lat, lon), 2.0)
            locs.append(_make_location(lat, lon, base_precip=base))
        return locs if len(locs) > 1 else locs[0]

    monkeypatch.setattr(lw, "_http_get_json", fake_get)
    lw.clear_cache()
    datasets.clear_live_cache()


def _fake_outage(monkeypatch, message="simulated provider outage"):
    def fail(url, timeout):
        raise LiveDataError(message)

    monkeypatch.setattr(lw, "_http_get_json", fail)
    lw.clear_cache()
    datasets.clear_live_cache()


# ------------------------------------------------------------- provider unit
def test_fetch_one_parses_response_into_model_features(monkeypatch):
    _fake_transport(monkeypatch)
    point = lw.fetch_one(12.5, 74.99)
    assert point.raw_nwp_mm > 0
    assert 0 <= point.humidity <= 100
    assert 900 < point.pressure < 1100
    assert point.window_hours == 24
    assert point.forecast_time
    assert point.fetched_at


def test_fetch_batch_caches_and_reuses(monkeypatch):
    _fake_transport(monkeypatch)
    coords = [(12.5, 74.99), (11.25, 75.78)]
    first = lw.fetch_batch(coords)
    second = lw.fetch_batch(coords)
    # Same object identity confirms the second call hit the cache rather than
    # re-fetching.
    assert first[coords[0]] is second[coords[0]]


def test_fetch_batch_refresh_bypasses_cache(monkeypatch):
    _fake_transport(monkeypatch, precip_by_coord={(1.0, 1.0): 5.0})
    first = lw.fetch_one(1.0, 1.0)

    # Swap only the transport function itself (not via _fake_transport, which
    # would also clear the cache we are trying to test).
    def fake_get(url, timeout):
        return _make_location(1.0, 1.0, base_precip=50.0)
    monkeypatch.setattr(lw, "_http_get_json", fake_get)

    cached = lw.fetch_one(1.0, 1.0)                      # should reuse the cached value
    refreshed = lw.fetch_one(1.0, 1.0, use_cache=False)  # forces a re-fetch

    assert cached.raw_nwp_mm == first.raw_nwp_mm
    assert refreshed.raw_nwp_mm != first.raw_nwp_mm


def test_missing_required_variable_raises_not_invents(monkeypatch):
    """If the provider ever drops a required variable, fail loudly."""
    def fake_get(url, timeout):
        loc = _make_location(1.0, 1.0)
        del loc["hourly"]["surface_pressure"]
        return loc

    monkeypatch.setattr(lw, "_http_get_json", fake_get)
    lw.clear_cache()
    with pytest.raises(LiveDataError, match="surface_pressure"):
        lw.fetch_one(1.0, 1.0)


def test_provider_outage_raises_live_data_error(monkeypatch):
    _fake_outage(monkeypatch)
    with pytest.raises(LiveDataError):
        lw.fetch_one(1.0, 1.0)


# ---------------------------------------------------------- feature assembly
def test_build_feature_frame_matches_model_input_columns(monkeypatch):
    from app.ml.features import RAW_INPUT_COLUMNS

    _fake_transport(monkeypatch)
    districts = datasets.get_districts()
    frame = lw.build_feature_frame(districts, refresh=True)
    assert len(frame) == len(districts)
    for col in RAW_INPUT_COLUMNS:
        assert col in frame.columns, f"live feature frame is missing model input '{col}'"
    assert (frame["raw_nwp_mm"] >= 0).all()


# -------------------------------------------------------------- full pipeline
def test_get_live_forecast_runs_the_real_trained_pipeline(monkeypatch):
    _fake_transport(monkeypatch)
    df = datasets.get_live_forecast(refresh=True)
    assert len(df) == len(datasets.get_districts())
    assert df["regime"].isin(REGIMES).all()
    assert (df["corrected_mm"] >= 0).all()
    assert df["condition"].isin(["LOW", "NORMAL", "MODERATE", "HEAVY", "VERY_HEAVY"]).all()
    assert df["data_source"].eq("Open-Meteo").all()
    assert df["forecast_time"].notna().all()
    assert df["fetched_at"].notna().all()


def test_get_live_forecast_propagates_outage(monkeypatch):
    _fake_outage(monkeypatch)
    with pytest.raises(LiveDataError):
        datasets.get_live_forecast(refresh=True)


def test_live_status_reflects_outage_and_recovery(monkeypatch):
    _fake_transport(monkeypatch)
    ok = datasets.live_status()
    assert ok["mode"] == "LIVE"
    assert ok["reachable"] is True

    _fake_outage(monkeypatch)
    down = datasets.live_status()
    assert down["mode"] == "UNAVAILABLE"
    assert down["reachable"] is False
    assert down["last_error"]
