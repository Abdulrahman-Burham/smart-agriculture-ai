"""Embedding backends.

* `sentence_transformers` (default): multilingual-e5, strong on Arabic, runs locally.
* `hash`: deterministic, dependency-free embedder for unit tests / offline CI only.
"""
from __future__ import annotations

import hashlib
import math
from functools import lru_cache
from typing import Protocol

from ..config import Settings
from ..nlp.arabic import strip_diacritics, tokenize


class Embedder(Protocol):
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...


class SentenceTransformerEmbedder:
    def __init__(self, model_name: str):
        from sentence_transformers import SentenceTransformer  # lazy: heavy import

        self._model = SentenceTransformer(model_name)
        self._e5 = "e5" in model_name.lower()  # e5 models need "query:" / "passage:" prefixes

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        prefix = "passage: " if self._e5 else ""
        vecs = self._model.encode([prefix + strip_diacritics(t) for t in texts],
                                  normalize_embeddings=True, batch_size=32, show_progress_bar=False)
        return vecs.tolist()

    @lru_cache(maxsize=2048)  # repeated / popular questions skip the encoder entirely
    def _cached_query(self, text: str) -> tuple[float, ...]:
        prefix = "query: " if self._e5 else ""
        vec = self._model.encode([prefix + strip_diacritics(text)], normalize_embeddings=True,
                                 show_progress_bar=False)[0]
        return tuple(vec.tolist())

    def embed_query(self, text: str) -> list[float]:
        return list(self._cached_query(text))


class HashEmbedder:
    """Bag-of-words + char-trigram hashing. Not semantic; good enough to exercise the pipeline."""

    def __init__(self, dim: int = 512):
        self.dim = dim

    def _vec(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for tok in tokenize(text):
            feats = [tok] + [tok[i:i + 3] for i in range(max(len(tok) - 2, 0))]
            for f in feats:
                h = int(hashlib.md5(f.encode()).hexdigest(), 16)
                vec[h % self.dim] += 1.0 if h & 1 else -1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vec(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vec(text)


def get_embedder(settings: Settings) -> Embedder:
    if settings.embedding_backend == "hash":
        return HashEmbedder()
    return SentenceTransformerEmbedder(settings.embedding_model)
