"""Embedding service wrapper for the configured embedding model."""

from __future__ import annotations

from typing import Any


class EmbeddingService:
    """Adapter for embedding models with a swappable model name."""

    def __init__(self, model_name: str = "BAAI/bge-m3", api_key: str | None = None):
        self.model_name = model_name
        self.api_key = api_key

    def embed_text(self, text: str) -> list[float]:
        """Return a simple deterministic vector for a text fragment."""

        if not text:
            return [0.0] * 384

        normalized = text.lower().strip()
        vector = [0.0] * 384
        for i, ch in enumerate(normalized[:384]):
            vector[i] = float(ord(ch) % 10) / 10.0
        return vector

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts."""

        return [self.embed_text(text) for text in texts]


def build_embedding_service(model_name: str, api_key: str | None = None) -> EmbeddingService:
    """Factory for constructing the configured embedding service."""

    return EmbeddingService(model_name=model_name, api_key=api_key)
