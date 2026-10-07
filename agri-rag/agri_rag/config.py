"""Central configuration. Every value can be overridden with an AGRI_* env var or .env file."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="AGRI_", extra="ignore")

    env: str = "dev"
    api_key: str | None = None  # when set, every /v1 call requires X-API-Key

    # --- LLM -------------------------------------------------------------
    llm_provider: str = "anthropic"  # anthropic | openai_compat | fake
    llm_model: str = "claude-haiku-4-5-20251001"  # small model => low time-to-first-token
    llm_api_key: str | None = None  # falls back to ANTHROPIC_API_KEY / OPENAI_API_KEY
    llm_base_url: str | None = None  # for Ollama / vLLM / any OpenAI-compatible server
    llm_max_tokens: int = 700
    llm_temperature: float = 0.2
    llm_timeout_s: float = 20.0

    # --- Embeddings / vector store ------------------------------------------
    embedding_backend: str = "sentence_transformers"  # sentence_transformers | hash
    embedding_model: str = "intfloat/multilingual-e5-base"
    chroma_dir: Path = ROOT / "storage" / "chroma"
    collection: str = "agri_knowledge"

    # --- Data ---------------------------------------------------------------
    knowledge_dir: Path = ROOT / "data" / "knowledge"
    glossary_path: Path = ROOT / "data" / "glossary" / "egyptian_agri_glossary.json"
    crop_profiles_path: Path = ROOT / "config" / "crop_profiles.yaml"

    # --- Chunking -----------------------------------------------------------
    chunk_max_chars: int = 900
    chunk_overlap_chars: int = 120

    # --- Retrieval ----------------------------------------------------------
    top_k: int = 5
    candidate_k: int = 20
    rrf_k: int = 60
    # Cosine similarity gate. MUST be calibrated with `python -m agri_rag.evaluation.run`
    # (it prints a suggested value from your golden set). 0 disables the gate.
    min_similarity: float = 0.78
    context_max_chars: int = 6000

    # --- Conversation -------------------------------------------------------
    session_max_turns: int = 30
    session_ttl_s: int = 604800  # 7 days persistent memory

    # --- Weather (automatic lookup when the app sends only a location) -----
    weather_enabled: bool = True
    weather_timeout_s: float = 2.0
    weather_cache_ttl_s: int = 1800

    # --- SLO ----------------------------------------------------------------
    latency_budget_s: float = 3.0  # project KPI: assistant latency <= 3 s


@lru_cache
def get_settings() -> Settings:
    return Settings()
