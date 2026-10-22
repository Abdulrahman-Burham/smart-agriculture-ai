"""System Health & Hardware Telemetry Schemas."""

from __future__ import annotations

from typing import Dict
from pydantic import BaseModel, Field

from app.core.config import APP_VERSION


class HealthResponse(BaseModel):
    status: str = Field("healthy", description="Application status")
    services: Dict[str, str] = Field(
        default_factory=dict, description="Component status map"
    )
    version: str = Field(APP_VERSION, description="Running platform version")


class HealthCheckResponse(BaseModel):
    """System health check and readiness status."""

    status: str = Field("healthy", examples=["healthy"])
    services: Dict[str, str] = Field(..., description="Services map")
    version: str = Field("1.0.0", examples=["1.0.0"])
