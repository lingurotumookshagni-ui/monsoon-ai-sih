"""Pydantic request/response models for the MonsoonAI API."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class WeatherFeatures(BaseModel):
    """Meteorological + geographic inputs for a single district/grid point.

    Only ``raw_nwp_mm`` is mandatory. Anything omitted is filled with
    climatological defaults (see app/ml/features.py) so a partial request
    still returns a usable answer instead of an error.
    """
    district: Optional[str] = Field(None, description="District or grid point name")
    state: Optional[str] = None
    raw_nwp_mm: float = Field(..., ge=0, le=2000,
                              description="Raw NWP 24 h rainfall forecast (mm)")
    humidity: Optional[float] = Field(None, ge=0, le=100, description="Relative humidity (%)")
    temperature: Optional[float] = Field(None, ge=-60, le=60, description="Air temperature (degC)")
    pressure: Optional[float] = Field(None, ge=500, le=1100, description="Station pressure (hPa)")
    wind_speed: Optional[float] = Field(None, ge=0, le=120, description="Wind speed (m/s)")
    wind_direction: Optional[float] = Field(None, ge=0, le=360, description="Wind direction (deg)")
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    elevation: Optional[float] = Field(None, ge=-500, le=9000, description="Elevation (m)")
    distance_from_coast: Optional[float] = Field(None, ge=0, le=3000,
                                                 description="Distance from coast (km)")
    month: Optional[int] = Field(None, ge=1, le=12)
    day_of_year: Optional[int] = Field(None, ge=1, le=366)
    regime: Optional[str] = Field(None, description="Override the classified regime")

    def to_row(self) -> Dict[str, Any]:
        """Drop unset values so feature defaults can fill the gaps."""
        data = self.dict() if hasattr(self, "dict") else self.model_dump()
        return {k: v for k, v in data.items() if v is not None}


class RegimeResponse(BaseModel):
    regime: str
    confidence: float
    probabilities: Dict[str, float]
    method: str
    disclaimer: str


class PostProcessResponse(BaseModel):
    district: Optional[str] = None
    state: Optional[str] = None
    regime: str
    regime_confidence: float
    raw_nwp_mm: float
    corrected_rainfall_mm: float
    correction_mm: float
    confidence: float
    category: str
    heavy_probability: float
    very_heavy_probability: float
    method: str
    data_source: str


class HeavyRainfallResponse(BaseModel):
    probability_heavy: float
    probability_very_heavy: float
    category: str
    risk_band: str
    expected_rainfall_mm: float
    raw_nwp_mm: float
    regime: str
    thresholds_mm: Dict[str, float]
    method: str


class ForecastRecord(BaseModel):
    district: str
    state: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    elevation: Optional[float] = None
    distance_from_coast: Optional[float] = None
    regime: str
    regime_confidence: float
    raw_nwp_mm: float
    corrected_mm: float
    correction_mm: float
    heavy_probability: float
    very_heavy_probability: float
    category: str
    raw_category: Optional[str] = None
    risk_band: Optional[str] = None
    humidity: Optional[float] = None
    temperature: Optional[float] = None
    pressure: Optional[float] = None
    wind_speed: Optional[float] = None
    wind_direction: Optional[float] = None
    forecast_date: Optional[str] = None
    observed_rainfall_mm: Optional[float] = None


class HealthResponse(BaseModel):
    status: str
    default_source: str
    demo_mode: bool
    banner: str
    models: Dict[str, Any]
    live: Dict[str, Any]
    districts_loaded: int
    data_source: str
    version: str


class UploadResponse(BaseModel):
    status: str
    rows_received: int
    rows_accepted: int
    has_observations: bool
    warnings: List[str]
    columns_detected: List[str]
    summary: Dict[str, Any]
    records: List[Dict[str, Any]]


class ErrorResponse(BaseModel):
    detail: str
    errors: Optional[List[str]] = None
