"""Unified FastAPI Gateway: Smart Agriculture AI Platform.

Clean, modular, layered architecture:
- Core: Configuration, security dependencies, guest access policy, silent telemetry
- Schemas: Pydantic request/response models with validation
- Services: LLM/RAG orchestration, computer vision, weather forecasting, speech processing
- Routers: Modular HTTP routes (pages, auth, chat, diagnose, weather, audio, dev)
- Storage: Thread-safe SQLite repository pattern with WAL mode
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import APP_VERSION, STATIC_DIR
from app.core.telemetry import SilentTelemetryMiddleware
from app.routers import (
    audio_router,
    auth_router,
    chat_router,
    dev_router,
    diagnose_router,
    pages_router,
    weather_router,
)
from app.schemas import *  # Backward compatibility re-export
from app.services.llm_service import (
    format_agri_rag_sources,
    get_rag_pipeline,
    query_agri_rag,
)
from app.services.vision_service import get_cv_classifier
from computer_vision.storage.connection import init_db

load_dotenv()
logger = logging.getLogger("smart_agri")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager: Initialize database and warm up models."""
    logger.info("Initializing Smart Agriculture AI Platform...")
    init_db()
    # Warm up CV classifier in background thread so the first prediction is instant
    asyncio.create_task(asyncio.to_thread(get_cv_classifier))
    yield
    logger.info("Smart Agriculture AI Platform shutting down cleanly.")


app = FastAPI(
    title="الخبير الزراعي — Smart Agriculture AI",
    description="Production Gateway: Agri-RAG + Computer Vision + Authentication + Dashboard",
    version=APP_VERSION,
    lifespan=lifespan,
)

# ─── Middleware ────────────────────────────────────────────────────────
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SilentTelemetryMiddleware)

# ─── Static Files ──────────────────────────────────────────────────────
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# ─── Modular Routers ───────────────────────────────────────────────────
app.include_router(pages_router)
app.include_router(auth_router)
app.include_router(weather_router)
app.include_router(chat_router)
app.include_router(diagnose_router)
app.include_router(audio_router)
app.include_router(dev_router)

__all__ = [
    "app",
    "get_cv_classifier",
    "get_rag_pipeline",
    "query_agri_rag",
    "format_agri_rag_sources",
]
