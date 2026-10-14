"""Application Configuration & Environment Settings.

Provides centralized typed settings, paths, and environment variable resolution.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Set

from dotenv import load_dotenv

load_dotenv()

BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
APP_DIR: Path = BASE_DIR / "app"
DATA_DIR: Path = BASE_DIR / "data"
STATIC_DIR: Path = APP_DIR / "static"
TEMPLATES_DIR: Path = APP_DIR / "templates"

AGRI_RAG_URL: str = os.environ.get("AGRI_RAG_URL", "http://127.0.0.1:8070")
DEV_SECRET_KEY: str = os.environ.get("DEV_SECRET_KEY", "abdo-dev-2026")
DEV_PANEL_KEY: str = os.environ.get("DEV_PANEL_KEY", "abdo-dev-2026")

APP_VERSION: str = "3.0.0-clean-architecture"

KNOWN_AGRI_RAG_CROPS: Set[str] = {
    "طماطم",
    "بطاطس",
    "ذرة",
    "قمح",
    "مانجو",
    "أرز",
}
