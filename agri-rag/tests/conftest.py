import uuid
from pathlib import Path

import pytest

from agri_rag.config import ROOT, Settings
from agri_rag.container import build_container
from agri_rag.generation.llm import FakeLLM
from agri_rag.ingestion.indexer import index_directory


@pytest.fixture()
def settings() -> Settings:
    return Settings(_env_file=None, embedding_backend="hash", llm_provider="fake", min_similarity=0.0, weather_enabled=False,
                    collection=f"test_{uuid.uuid4().hex[:8]}", knowledge_dir=ROOT / "data" / "knowledge")


@pytest.fixture()
def container(settings):
    c = build_container(settings, llm=FakeLLM(), persistent=False)
    index_directory(settings.knowledge_dir, c.store, settings, reset=True)
    c.retriever.refresh()
    return c
