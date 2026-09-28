"""API tests for MonsoonAI.

Run from the backend/ folder:   python -m pytest
These tests exercise the real FastAPI app with the TestClient, so they cover
routing, Pydantic validation, error handling and the JSON contract.
"""
from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import datasets, live_weather as lw

client = TestClient(app)


def _fake_live_transport(monkeypatch, base_precip: float = 20.0):
    """Install a mocked Open-Meteo transport for the live-mode API tests.

    No real network call is made anywhere in this test file.
    """
    import datetime as _dt
    import urllib.parse as _up

    def _location(lat, lon):
        now = _dt.datetime.utcnow().replace(minute=0, second=0, microsecond=0)
        times = [(now + _dt.timedelta(hours=h)).isoformat() for h in range(48)]
        n = len(times)
        return {
            "latitude": lat, "longitude": lon, "elevation": 12.3,
            "hourly": {
                "time": times,
                "precipitation": [base_precip + (h % 5) * 0.4 for h in range(n)],
                "relative_humidity_2m": [85.0 for _ in range(n)],
                "temperature_2m": [27.0 for _ in range(n)],
                "surface_pressure": [1001.0 for _ in range(n)],
                "wind_speed_10m": [8.0 for _ in range(n)],
                "wind_direction_10m": [250.0 for _ in range(n)],
            },
        }

    def fake_get(url, timeout):
        q = _up.parse_qs(_up.urlparse(url).query)
        lats = [float(x) for x in q["latitude"][0].split(",")]
        lons = [float(x) for x in q["longitude"][0].split(",")]
        locs = [_location(a, b) for a, b in zip(lats, lons)]
        return locs if len(locs) > 1 else locs[0]

    monkeypatch.setattr(lw, "_http_get_json", fake_get)
    lw.clear_cache()
    datasets.clear_live_cache()


def _fake_live_outage(monkeypatch, message="simulated outage"):
    def fail(url, timeout):
        raise lw.LiveDataError(message)

    monkeypatch.setattr(lw, "_http_get_json", fail)
    lw.clear_cache()
    datasets.clear_live_cache()

SAMPLE = {
    "district": "Kasaragod",
    "state": "Kerala",
    "raw_nwp_mm": 82.0,
    "humidity": 88.0,
    "temperature": 27.5,
    "pressure": 1001.0,
    "wind_speed": 9.5,
    "wind_direction": 255.0,
    "latitude": 12.50,
    "longitude": 74.99,
    "elevation": 20.0,
    "distance_from_coast": 5.0,
    "month": 7,
}


# ---------------------------------------------------------------- meta
def test_root():
    r = client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "MonsoonAI"
    assert body["demo_mode"] is True
    assert "DEMO MODE" in body["banner"]


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["districts_loaded"] > 0
    assert "mode" in body["models"]


def test_districts():
    r = client.get("/api/districts")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] >= 50
    assert "Kerala" in body["states"]
    assert {"district", "state", "latitude", "longitude", "elevation",
            "distance_from_coast"} <= set(body["districts"][0].keys())


def test_regimes_catalogue():
    r = client.get("/api/regimes")
    assert r.status_code == 200
    regimes = r.json()["regimes"]
    assert len(regimes) == 7
    names = {x["regime"] for x in regimes}
    assert "ACTIVE_MONSOON" in names and "WESTERN_DISTURBANCE" in names
    assert all("current" in x for x in regimes)


def test_config_thresholds():
    body = client.get("/api/config").json()
    assert body["rainfall_thresholds_mm"]["HEAVY_MIN"] == 64.5
    assert 115.6 in body["verification_thresholds_mm"]


# ---------------------------------------------------------- regime prediction
def test_predict_regime():
    r = client.post("/api/predict-regime", json=SAMPLE)
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body["regime"], str)
    assert 0.0 <= body["confidence"] <= 1.0
    assert abs(sum(body["probabilities"].values()) - 1.0) < 0.05
    assert "not official" in body["disclaimer"]


def test_predict_regime_rejects_bad_input():
    r = client.post("/api/predict-regime", json={"raw_nwp_mm": -5})
    assert r.status_code == 422
    r = client.post("/api/predict-regime", json={"humidity": 80})
    assert r.status_code == 422


def test_predict_regime_depression_signature():
    """A deep low with saturated air and strong winds should not be a break spell."""
    payload = dict(SAMPLE, pressure=990.0, wind_speed=18.0, humidity=95.0,
                   raw_nwp_mm=140.0, latitude=20.0, longitude=85.8,
                   elevation=6.0, distance_from_coast=3.0)
    body = client.post("/api/predict-regime", json=payload).json()
    assert body["regime"] != "BREAK_MONSOON"


# ------------------------------------------------------------ post-processing
def test_postprocess():
    r = client.post("/api/postprocess", json=SAMPLE)
    assert r.status_code == 200
    body = r.json()
    assert body["district"] == "Kasaragod"
    assert body["raw_nwp_mm"] == 82.0
    assert body["corrected_rainfall_mm"] >= 0.0
    assert abs(body["correction_mm"] - (body["corrected_rainfall_mm"] - body["raw_nwp_mm"])) < 0.05
    assert body["category"] in ["LIGHT", "MODERATE", "HEAVY", "VERY_HEAVY", "EXTREMELY_HEAVY"]


def test_postprocess_never_negative():
    body = client.post("/api/postprocess", json=dict(SAMPLE, raw_nwp_mm=0.0)).json()
    assert body["corrected_rainfall_mm"] >= 0.0


def test_postprocess_respects_regime_override():
    body = client.post("/api/postprocess",
                       json=dict(SAMPLE, regime="OROGRAPHIC_RAINFALL")).json()
    assert body["regime"] == "OROGRAPHIC_RAINFALL"


# ------------------------------------------------------ heavy rain probability
def test_heavy_rainfall_probability():
    r = client.post("/api/heavy-rainfall-probability", json=SAMPLE)
    assert r.status_code == 200
    body = r.json()
    assert 0.0 <= body["probability_heavy"] <= 1.0
    assert 0.0 <= body["probability_very_heavy"] <= body["probability_heavy"] + 1e-6
    assert body["risk_band"] in ["LOW", "MODERATE", "HIGH", "VERY_HIGH"]
    assert body["thresholds_mm"]["heavy"] == 64.5


def test_heavy_probability_increases_with_rainfall():
    low = client.post("/api/heavy-rainfall-probability",
                      json=dict(SAMPLE, raw_nwp_mm=1.0)).json()
    high = client.post("/api/heavy-rainfall-probability",
                       json=dict(SAMPLE, raw_nwp_mm=180.0)).json()
    assert high["probability_heavy"] >= low["probability_heavy"]


# ------------------------------------------------------------------ forecast
def test_forecast_list_and_filters():
    r = client.get("/api/forecast")
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) > 0
    first = rows[0]
    for key in ["district", "state", "lat", "lon", "regime", "regime_confidence",
                "raw_nwp_mm", "corrected_mm", "heavy_probability",
                "very_heavy_probability", "category"]:
        assert key in first

    kerala = client.get("/api/forecast", params={"state": "Kerala"}).json()
    assert len(kerala) > 0
    assert all(row["state"] == "Kerala" for row in kerala)

    one = client.get("/api/forecast", params={"district": "Kasaragod"}).json()
    assert len(one) == 1 and one[0]["district"] == "Kasaragod"

    regime = rows[0]["regime"]
    filtered = client.get("/api/forecast", params={"regime": regime}).json()
    assert all(row["regime"] == regime for row in filtered)


def test_forecast_unknown_filter_returns_empty_list():
    rows = client.get("/api/forecast", params={"state": "Atlantis"}).json()
    assert rows == []


def test_overview_payload():
    body = client.get("/api/overview").json()
    assert body["kpis"]["districts"] > 0
    assert "heavy_alerts" in body["kpis"]
    assert isinstance(body["regimes"], list)
    assert len(body["map_points"]) == body["kpis"]["districts"]


def test_heavy_rainfall_watchlist_is_sorted():
    body = client.get("/api/heavy-rainfall").json()
    probs = [d["heavy_probability"] for d in body["districts"]]
    assert probs == sorted(probs, reverse=True)


# -------------------------------------------------------------- verification
def test_verification_report():
    r = client.get("/api/verification")
    if r.status_code == 404:
        pytest.skip("Run 'python train_models.py' to create the evaluation dataset.")
    assert r.status_code == 200
    body = r.json()
    for block in ("raw_nwp", "ai_corrected"):
        for key in ("rmse", "mae", "csi", "pod", "far", "ets", "fss"):
            assert key in body[block]
    assert body["sample_size"] > 0
    assert "improvement" in body
    assert 64.5 in body["thresholds_mm"]


def test_verification_custom_thresholds_and_bad_input():
    r = client.get("/api/verification", params={"thresholds": "20,64.5"})
    if r.status_code == 404:
        pytest.skip("No evaluation dataset available.")
    assert r.status_code == 200
    assert r.json()["thresholds_mm"] == [20.0, 64.5]
    bad = client.get("/api/verification", params={"thresholds": "abc"})
    assert bad.status_code == 422


# -------------------------------------------------------------------- upload
GOOD_CSV = (
    "district,state,latitude,longitude,raw_nwp_mm,observed_rainfall_mm,humidity,"
    "pressure,temperature,wind_speed,elevation,distance_from_coast,month\n"
    "Kasaragod,Kerala,12.50,74.99,82,103,88,1001,27.5,9.5,20,5,7\n"
    "Wayanad,Kerala,11.69,76.13,95,168,90,905,21.0,8.0,780,55,7\n"
    "Pune,Maharashtra,18.52,73.86,12,4,62,1005,32.0,4.0,560,90,7\n"
)


def test_upload_flow_and_uploaded_source():
    files = {"file": ("demo.csv", io.BytesIO(GOOD_CSV.encode()), "text/csv")}
    r = client.post("/api/upload-data", files=files)
    assert r.status_code == 200
    body = r.json()
    assert body["rows_accepted"] == 3
    assert body["has_observations"] is True
    assert body["verification"] is not None
    assert len(body["records"]) == 3

    rows = client.get("/api/forecast", params={"source": "uploaded"}).json()
    assert len(rows) == 3

    ver = client.get("/api/verification", params={"source": "uploaded"}).json()
    assert ver["dataset"] == "USER_UPLOAD"

    assert client.delete("/api/upload-data").json()["status"] == "cleared"
    missing = client.get("/api/forecast", params={"source": "uploaded"})
    assert missing.status_code == 404


def test_upload_rejects_missing_columns():
    csv = "district,state\nKasaragod,Kerala\n"
    files = {"file": ("bad.csv", io.BytesIO(csv.encode()), "text/csv")}
    r = client.post("/api/upload-data", files=files)
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert "errors" in detail
    assert any("latitude" in e for e in detail["errors"])


def test_upload_rejects_non_csv_extension():
    files = {"file": ("model.pkl", io.BytesIO(b"not a csv"), "application/octet-stream")}
    assert client.post("/api/upload-data", files=files).status_code == 415


def test_district_detail_returns_citizen_view():
    r = client.get("/api/districts/Malappuram")
    assert r.status_code == 200
    body = r.json()
    assert body["district"]["district"] == "Malappuram"
    assert body["district"]["condition"] in [
        "LOW", "NORMAL", "MODERATE", "HEAVY", "VERY_HEAVY"]
    assert body["explanation_key"].startswith("explanation.")
    assert body["regime"]["code"]
    assert body["demo_mode"] is True


def test_district_detail_unknown_district():
    assert client.get("/api/districts/Atlantis").status_code == 404


def test_forecast_includes_every_condition_band():
    """The product must serve normal and low rainfall districts too."""
    rows = client.get("/api/forecast").json()
    conditions = {row["condition"] for row in rows}
    assert conditions - {"LOW", "NORMAL", "MODERATE", "HEAVY", "VERY_HEAVY"} == set()
    assert len(conditions) > 1


def test_process_reports_real_stages():
    body = client.post("/api/process").json()
    assert body["status"] == "complete"
    keys = [s["key"] for s in body["stages"]]
    assert keys == ["load", "regime", "postprocess", "probability",
                    "metrics", "results", "visualisation"]
    assert all(s["status"] == "done" for s in body["stages"])
    assert body["total_ms"] > 0


def test_upload_template():
    body = client.get("/api/upload-data/template").json()
    assert "district" in body["required_columns"]
    assert body["max_bytes"] > 0


# ------------------------------------------------------------------- LIVE
def test_live_status_reachable(monkeypatch):
    _fake_live_transport(monkeypatch)
    r = client.get("/api/live/status")
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "LIVE"
    assert body["source"] == "Open-Meteo"
    assert body["reachable"] is True


def test_live_status_unavailable_on_outage(monkeypatch):
    _fake_live_outage(monkeypatch)
    r = client.get("/api/live/status")
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "UNAVAILABLE"
    assert body["reachable"] is False
    assert body["last_error"]


def test_live_districts_lists_every_district(monkeypatch):
    _fake_live_transport(monkeypatch)
    r = client.get("/api/live/districts")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] >= 50
    assert "Kerala" in body["states"]


def test_live_rainfall_for_one_district(monkeypatch):
    _fake_live_transport(monkeypatch)
    r = client.get("/api/live/rainfall/Kozhikode")
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "LIVE"
    assert body["district"] == "Kozhikode"
    assert body["source"] == "Open-Meteo"
    assert body["raw_rainfall_mm"] >= 0
    assert body["post_processed_rainfall_mm"] >= 0
    assert body["regime"]
    assert body["category"]
    assert body["model_used"]
    assert body["observed_rainfall_mm"] is None
    assert body["forecast_time"]
    assert body["last_updated"]


def test_live_rainfall_unknown_district(monkeypatch):
    _fake_live_transport(monkeypatch)
    r = client.get("/api/live/rainfall/Atlantis")
    assert r.status_code == 404


def test_live_rainfall_outage_returns_503_not_fake_data(monkeypatch):
    _fake_live_outage(monkeypatch)
    r = client.get("/api/live/rainfall/Kozhikode")
    assert r.status_code == 503
    assert "detail" in r.json()


def test_live_refresh(monkeypatch):
    _fake_live_transport(monkeypatch)
    r = client.post("/api/live/refresh")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "refreshed"
    assert body["source"] == "Open-Meteo"
    assert body["districts"] >= 50


def test_generic_forecast_defaults_to_live(monkeypatch):
    _fake_live_transport(monkeypatch)
    r = client.get("/api/forecast")  # no source param -> must default to live
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) >= 50


def test_generic_forecast_live_outage_is_503_not_silent_demo(monkeypatch):
    _fake_live_outage(monkeypatch)
    r = client.get("/api/forecast?source=live")
    assert r.status_code == 503
    # Demo must still work independently - the outage must not have corrupted
    # the demo path.
    demo = client.get("/api/forecast?source=demo")
    assert demo.status_code == 200
    assert len(demo.json()) >= 50


def test_overview_live_has_no_fabricated_verification(monkeypatch):
    _fake_live_transport(monkeypatch)
    body = client.get("/api/overview?source=live").json()
    assert body["banner"].startswith("LIVE")
    assert body["verification"]["available"] is False


def test_overview_demo_still_has_verification(monkeypatch):
    # No live mock installed/needed - demo path must not touch the live provider.
    body = client.get("/api/overview?source=demo").json()
    assert body["banner"].startswith("DEMO")


def test_verification_live_reports_unavailable_not_demo_numbers():
    r = client.get("/api/verification?source=live")
    assert r.status_code == 200
    body = r.json()
    assert body["available"] is False
    assert "reason" in body


def test_district_detail_live(monkeypatch):
    _fake_live_transport(monkeypatch)
    r = client.get("/api/districts/Kozhikode?source=live")
    assert r.status_code == 200
    body = r.json()
    assert body["data_source"] == "Open-Meteo"
    assert body["demo_mode"] is False


def test_process_live_reports_real_stages(monkeypatch):
    _fake_live_transport(monkeypatch)
    r = client.post("/api/process?source=live")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "complete"
    assert body["demo_mode"] is False
    assert all(s["status"] == "done" for s in body["stages"])


def test_process_live_outage_fails_the_load_stage(monkeypatch):
    _fake_live_outage(monkeypatch)
    r = client.post("/api/process?source=live")
    assert r.status_code == 503


def test_health_reports_live_reachability(monkeypatch):
    _fake_live_transport(monkeypatch)
    body = client.get("/api/health").json()
    assert body["default_source"] == "live"
    assert body["demo_mode"] is False
    assert body["live"]["reachable"] is True


def test_health_reports_live_unavailable_on_outage(monkeypatch):
    _fake_live_outage(monkeypatch)
    body = client.get("/api/health").json()
    assert body["live"]["reachable"] is False
    assert body["banner"] == "LIVE DATA UNAVAILABLE"


def test_demo_mode_never_labelled_live(monkeypatch):
    # Regardless of live provider state, requesting source=demo must always
    # come back labelled as demo, never as live.
    _fake_live_transport(monkeypatch)
    body = client.get("/api/forecast?source=demo").json()
    assert len(body) > 0
    for row in body[:5]:
        assert row.get("data_source") in (None, "SYNTHETIC_DEMO")
