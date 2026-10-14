"""Application Routers Package."""

from app.routers.audio import router as audio_router
from app.routers.auth import router as auth_router
from app.routers.chat import router as chat_router
from app.routers.dev import router as dev_router
from app.routers.diagnose import router as diagnose_router
from app.routers.pages import router as pages_router
from app.routers.weather import router as weather_router

__all__ = [
    "pages_router",
    "auth_router",
    "weather_router",
    "chat_router",
    "diagnose_router",
    "audio_router",
    "dev_router",
]
