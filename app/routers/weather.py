"""Weather & System Health Endpoints.

Provides:
- GET /health and HEAD /health: System readiness and microservices health check
- GET /api/public-stats: Public platform statistics for landing page counters
- GET /api/weather: Current Egyptian weather, GPS reverse geocoding, and season
"""

from __future__ import annotations

import asyncio
import datetime
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, Query, Request

from app.schemas.system import HealthResponse
from app.schemas.weather import WeatherResponse
from app.services.vision_service import get_cv_classifier
from app.services.weather_service import (
    EGYPT_GOV_COORDS,
    _WEATHER_CACHE,
    fetch_weather_forecast,
    get_public_platform_stats,
    nearest_governorate,
)
from computer_vision.storage.telemetry_repository import get_developer_analytics
from computer_vision.storage.user_repository import (
    get_pinned_visitor_profile,
    save_pinned_location_and_prefs,
)
from computer_vision.storage.utils import extract_client_info, extract_user_from_request

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["System"])
@router.head("/health", response_model=HealthResponse, tags=["System"])
async def health_check() -> HealthResponse:
    """System health and readiness probe."""
    cv = get_cv_classifier()
    return HealthResponse(
        status="healthy",
        services={
            "api_gateway": "online",
            "agri_rag": "online",
            "rag_pipeline": "online",
            "cv_model": "online" if cv else "offline",
            "vector_store": "chroma_hybrid_e5_bm25",
        },
    )


@router.get("/api/public-stats", tags=["System"])
async def public_stats_endpoint() -> Dict[str, Any]:
    """Return safe, anonymized live platform statistics for the Landing Page and Demo Day showcase."""
    return await get_public_platform_stats()


@router.get("/api/weather", response_model=WeatherResponse, tags=["Tools"])
async def get_weather_endpoint(
    http_request: Request,
    governorate: Optional[str] = Query(None),
    gov: Optional[str] = Query(None),
    lat: Optional[float] = Query(None),
    lon: Optional[float] = Query(None),
    pin: bool = Query(True),
) -> WeatherResponse:
    """Get current weather and agricultural season by GPS, manual governorate, or the user's cookie-pinned location."""
    client_info = extract_client_info(http_request)
    token_user = extract_user_from_request(http_request)
    u_id = int(token_user["uid"]) if token_user and token_user.get("uid") else None

    explicit_gov = (gov or governorate or "").strip()
    is_gps = lat is not None and lon is not None and (-90 <= lat <= 90) and (-180 <= lon <= 180)
    loc_source = "manual"

    if is_gps:
        gov_key = nearest_governorate(float(lat), float(lon))
        q_lat, q_lon = round(float(lat), 4), round(float(lon), 4)
        loc_source = "gps"
        if pin:
            await asyncio.to_thread(
                save_pinned_location_and_prefs,
                visitor_id=client_info["visitor_hash"],
                user_id=u_id,
                governorate=gov_key,
                gps_lat=q_lat,
                gps_lon=q_lon,
                location_source="gps",
                client_ip=client_info["client_ip"],
                device_type=client_info["device_type"],
            )
        return await fetch_weather_forecast(governorate=gov_key, lat=q_lat, lon=q_lon, location_source=loc_source)

    elif explicit_gov:
        gov_key = explicit_gov
        loc_source = "manual"
        if pin:
            await asyncio.to_thread(
                save_pinned_location_and_prefs,
                visitor_id=client_info["visitor_hash"],
                user_id=u_id,
                governorate=gov_key,
                location_source="manual",
                client_ip=client_info["client_ip"],
                device_type=client_info["device_type"],
            )
        return await fetch_weather_forecast(governorate=gov_key, location_source=loc_source)

    else:
        # Restore from cookie/DB pinned location so IP never overrides the farmer's real governorate
        pinned = await asyncio.to_thread(get_pinned_visitor_profile, client_info["visitor_hash"], u_id)
        if pinned.get("gps_lat") is not None and pinned.get("gps_lon") is not None:
            q_lat, q_lon = round(float(pinned["gps_lat"]), 4), round(float(pinned["gps_lon"]), 4)
            gov_key = pinned.get("governorate") or nearest_governorate(q_lat, q_lon)
            loc_source = pinned.get("location_source") or "gps"
            return await fetch_weather_forecast(governorate=gov_key, lat=q_lat, lon=q_lon, location_source=loc_source)
        else:
            gov_key = pinned.get("governorate") or "القاهرة"
            loc_source = pinned.get("location_source") or "pinned"
            return await fetch_weather_forecast(governorate=gov_key, location_source=loc_source)
