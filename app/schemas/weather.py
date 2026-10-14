"""Weather & Agricultural Meteorology Schemas."""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class WeatherResponse(BaseModel):
    temperature: Optional[float] = Field(None, description="Current temperature in Celsius")
    wind_speed: Optional[float] = Field(None, description="Wind speed in km/h")
    windspeed: Optional[float] = Field(None, description="Wind speed alias")
    humidity: Optional[float] = Field(None, description="Relative humidity percentage")
    governorate: str = Field("القاهرة", description="Egyptian governorate name")
    season: str = Field("", description="Current agricultural season")
    date: str = Field("", description="Date context")
    is_gps: bool = Field(False, description="Whether coordinates originate from device GPS")
    source: str = Field("governorate", description="gps | governorate | ip")
    lat: Optional[float] = Field(None, description="Latitude")
    lon: Optional[float] = Field(None, description="Longitude")
