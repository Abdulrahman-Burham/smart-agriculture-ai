"""Application settings and configuration for the agricultural RAG assistant."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]


def _get_bool(value: str, default: bool = False) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"} if value is not None else default


@dataclass
class Settings:
    """Centralized application configuration."""

    environment: str = os.getenv("ENVIRONMENT", "development")
    llm_provider: str = os.getenv("LLM_PROVIDER", "openai")
    llm_model_name: str = os.getenv("LLM_MODEL_NAME", "gpt-4o-mini")
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
    embedding_api_key: str = os.getenv("EMBEDDING_API_KEY", "")
    vector_db_type: str = os.getenv("VECTOR_DB_TYPE", "chroma")
    vector_db_url: str = os.getenv("VECTOR_DB_URL", "")
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///smart_agriculture.db")

    chunk_size: int = int(os.getenv("CHUNK_SIZE", "500"))
    chunk_overlap: int = int(os.getenv("CHUNK_OVERLAP", "75"))
    retrieval_top_k: int = int(os.getenv("RETRIEVAL_TOP_K", "20"))
    rerank_top_k: int = int(os.getenv("RERANK_TOP_K", "5"))
    confidence_threshold: float = float(os.getenv("CONFIDENCE_THRESHOLD", "0.35"))
    bm25_k: int = int(os.getenv("BM25_K", "60"))
    llm_fallback_rewrite: bool = _get_bool(os.getenv("LLM_FALLBACK_REWRITE"), True)

    retrieval_weights: dict[str, float] = field(
        default_factory=lambda: {"vector": 0.6, "bm25": 0.4}
    )
    dosage_lookup_weights: dict[str, float] = field(
        default_factory=lambda: {"vector": 0.4, "bm25": 0.6}
    )
    supported_crops: list[str] = field(
        default_factory=lambda: [
            "tomato",
            "wheat",
            "cotton",
            "cucumber",
            "pepper",
            "maize",
            "rice",
            "orange",
            "grape",
            "onion",
        ]
    )
    supported_diseases: list[str] = field(
        default_factory=lambda: [
            "blight",
            "fusarium",
            "powdery_mildew",
            "rust",
            "aphids",
            "nematodes",
            "root_rot",
        ]
    )
    region_options: list[str] = field(
        default_factory=lambda: ["delta", "upper_egypt", "nile_valley", "desert", "coastal"]
    )

    @property
    def project_root(self) -> Path:
        return ROOT_DIR


def get_settings() -> Settings:
    """Return a settings instance."""

    return Settings()
