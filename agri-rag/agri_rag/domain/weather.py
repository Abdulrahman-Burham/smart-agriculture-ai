"""Automatic weather lookup for the assistant.

If the app sends `farm.weather`, that always wins (it may come from a real sensor). Otherwise, when the
farm has coordinates (or just a governorate name) we fetch current conditions + rain forecast from
Open-Meteo (free, no API key). Weather is a *best-effort* enrichment: short timeout, cached, and any
failure simply means "no weather" — it must never slow down or break an answer.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from typing import Protocol

import httpx

from ..nlp.arabic import normalize_arabic
from .farm import FarmContext, WeatherSnapshot

log = logging.getLogger(__name__)

# Approximate centre (capital city) of each governorate: (latitude, longitude).
GOVERNORATE_COORDS: dict[str, tuple[float, float]] = {
    "القاهرة": (30.04, 31.24), "الجيزة": (30.01, 31.21), "الإسكندرية": (31.20, 29.92),
    "الدقهلية": (31.04, 31.38), "الشرقية": (30.59, 31.50), "الغربية": (30.79, 31.00),
    "المنوفية": (30.56, 31.01), "القليوبية": (30.46, 31.18), "البحيرة": (31.04, 30.47),
    "كفر الشيخ": (31.11, 30.94), "دمياط": (31.42, 31.81), "بورسعيد": (31.27, 32.30),
    "الإسماعيلية": (30.59, 32.27), "السويس": (29.97, 32.55), "الفيوم": (29.31, 30.84),
    "بني سويف": (29.07, 31.10), "المنيا": (28.11, 30.75), "أسيوط": (27.18, 31.18),
    "سوهاج": (26.56, 31.70), "قنا": (26.16, 32.72), "الأقصر": (25.69, 32.64),
    "أسوان": (24.09, 32.90), "الوادي الجديد": (25.45, 30.55), "مطروح": (31.35, 27.24),
    "شمال سيناء": (31.13, 33.80), "جنوب سيناء": (28.24, 33.62), "البحر الأحمر": (27.26, 33.81),
}
_NORMALISED = {normalize_arabic(name): coords for name, coords in GOVERNORATE_COORDS.items()}


def locate(farm: FarmContext) -> tuple[float, float] | None:
    """Exact coordinates if given, otherwise the governorate centre."""
    if farm.latitude is not None and farm.longitude is not None:
        return farm.latitude, farm.longitude
    if farm.governorate:
        text = normalize_arabic(farm.governorate)
        for name, coords in _NORMALISED.items():
            if name in text:
                return coords
    return None


class WeatherProvider(Protocol):
    async def current(self, lat: float, lon: float) -> WeatherSnapshot | None: ...


class OpenMeteoProvider:
    URL = "https://api.open-meteo.com/v1/forecast"

    def __init__(self, timeout_s: float = 2.0, cache_ttl_s: int = 1800,
                 transport: httpx.AsyncBaseTransport | None = None):
        self.timeout_s, self.cache_ttl_s, self._transport = timeout_s, cache_ttl_s, transport
        self._cache: dict[tuple[float, float], tuple[float, WeatherSnapshot]] = {}

    @staticmethod
    def _parse(data: dict) -> WeatherSnapshot:
        cur = data["current"]
        now = datetime.fromisoformat(cur["time"])
        times = [datetime.fromisoformat(t) for t in data["hourly"]["time"]]
        rain = data["hourly"]["precipitation"]
        past = sum((p or 0) for t, p in zip(times, rain) if now - timedelta(hours=24) < t <= now)
        ahead = sum((p or 0) for t, p in zip(times, rain) if now < t <= now + timedelta(hours=48))
        return WeatherSnapshot(
            temp_c=cur.get("temperature_2m"), humidity_pct=cur.get("relative_humidity_2m"),
            rain_mm_24h=round(past, 1), forecast_rain_mm_48h=round(ahead, 1),
            source="open-meteo", observed_at=cur["time"],
        )

    async def current(self, lat: float, lon: float) -> WeatherSnapshot | None:
        key = (round(lat, 2), round(lon, 2))  # ~1 km grid: nearby farms share one cached call
        hit = self._cache.get(key)
        if hit and time.time() - hit[0] < self.cache_ttl_s:
            return hit[1]
        params = {"latitude": lat, "longitude": lon, "timezone": "auto",
                  "current": "temperature_2m,relative_humidity_2m", "hourly": "precipitation",
                  "past_days": 1, "forecast_days": 3}
        try:
            async with httpx.AsyncClient(timeout=self.timeout_s, transport=self._transport) as client:
                resp = await client.get(self.URL, params=params)
                resp.raise_for_status()
                snapshot = self._parse(resp.json())
        except Exception as exc:  # network, HTTP status, or unexpected payload: degrade silently
            log.warning("weather lookup failed (%s); continuing without weather", type(exc).__name__)
            return None
        self._cache[key] = (time.time(), snapshot)
        return snapshot


class WeatherService:
    def __init__(self, provider: WeatherProvider, enabled: bool = True):
        self.provider, self.enabled = provider, enabled

    async def enrich(self, farm: FarmContext | None) -> FarmContext | None:
        """Return the farm with weather filled in when possible. Never raises, never overrides app data."""
        if farm is None or not self.enabled or farm.weather is not None:
            return farm
        where = locate(farm)
        if where is None:
            return farm
        snapshot = await self.provider.current(*where)
        return farm.model_copy(update={"weather": snapshot}) if snapshot else farm
