"""App Core Module: Configuration, Security, Guest Policy, Telemetry, and Rate Limiting."""

from app.core.config import (
    AGRI_RAG_URL,
    APP_DIR,
    APP_VERSION,
    BASE_DIR,
    DATA_DIR,
    DEV_PANEL_KEY,
    DEV_SECRET_KEY,
    KNOWN_AGRI_RAG_CROPS,
    STATIC_DIR,
    TEMPLATES_DIR,
)
from app.core.guest_policy import (
    enforce_guest_gate_or_401,
    load_guest_policy,
    save_guest_policy,
)
from app.core.rate_limiter import (
    RateLimiter,
    ai_audio_limiter,
    ai_chat_limiter,
    ai_diagnose_limiter,
)
from app.core.security import verify_dev_key
from app.core.telemetry import SilentTelemetryMiddleware

__all__ = [
    "BASE_DIR",
    "APP_DIR",
    "DATA_DIR",
    "STATIC_DIR",
    "TEMPLATES_DIR",
    "AGRI_RAG_URL",
    "DEV_SECRET_KEY",
    "DEV_PANEL_KEY",
    "APP_VERSION",
    "KNOWN_AGRI_RAG_CROPS",
    "verify_dev_key",
    "load_guest_policy",
    "save_guest_policy",
    "enforce_guest_gate_or_401",
    "SilentTelemetryMiddleware",
    "RateLimiter",
    "ai_diagnose_limiter",
    "ai_chat_limiter",
    "ai_audio_limiter",
]
