"""Weather & Agricultural Meteorology Schemas."""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class AgronomicAlert(BaseModel):
    """Early warning alert for agricultural diseases or extreme weather hazards."""
    id: str = Field(..., description="Unique alert identifier")
    title: str = Field(..., description="Alert headline in Arabic")
    level: str = Field("warning", description="info | warning | danger")
    disease_or_hazard: str = Field(..., description="Affected crop disease or climatic event")
    target_crops: List[str] = Field(default_factory=list, description="Targeted crop names")
    advice: str = Field(..., description="Preventive spray or cultural practice advice")
    icon: str = Field("⚠️", description="Emoji badge icon")


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
    alerts: List[AgronomicAlert] = Field(default_factory=list, description="Active agronomic early warning alerts")
