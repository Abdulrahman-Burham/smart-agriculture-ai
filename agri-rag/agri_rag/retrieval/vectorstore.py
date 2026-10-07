"""ChromaDB-backed vector store (persistent, cosine)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import chromadb

from ..ingestion.chunking import Chunk
from .embeddings import Embedder

GENERAL_CROP = "عام"


@dataclass
class Hit:
    chunk_id: str
    text: str
    metadata: dict
    similarity: float | None = None  # cosine similarity in [0, 1]; None if not scored by the vector index


class ChromaStore:
    def __init__(self, path: Path | None, collection: str, embedder: Embedder):
        self._embedder = embedder
        self._client = chromadb.PersistentClient(path=str(path)) if path else chromadb.EphemeralClient()
        self._col = self._client.get_or_create_collection(collection, metadata={"hnsw:space": "cosine"})
        self._collection_name = collection

    # -- write ------------------------------------------------------------------
    def upsert(self, chunks: list[Chunk], batch_size: int = 64) -> None:
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            self._col.upsert(
                ids=[c.id for c in batch],
                documents=[c.text for c in batch],
                embeddings=self._embedder.embed_documents([c.text for c in batch]),
                metadatas=[c.metadata for c in batch],
            )

    def delete_source(self, source: str) -> None:
        self._col.delete(where={"source": source})

    def reset(self) -> None:
        self._client.delete_collection(self._collection_name)
        self._col = self._client.get_or_create_collection(self._collection_name, metadata={"hnsw:space": "cosine"})

    # -- read -------------------------------------------------------------------
    @staticmethod
    def _crop_filter(crop: str | None) -> dict | None:
        return {"crop": {"$in": [crop, GENERAL_CROP]}} if crop and crop != GENERAL_CROP else None

    def query(self, vector: list[float], n: int, crop: str | None = None) -> list[Hit]:
        total = self._col.count()
        if total == 0:
            return []
        res = self._col.query(query_embeddings=[vector], n_results=min(n, total),
                              where=self._crop_filter(crop), include=["documents", "metadatas", "distances"])
        return [
            Hit(i, d, m, max(0.0, 1.0 - dist))
            for i, d, m, dist in zip(res["ids"][0], res["documents"][0], res["metadatas"][0], res["distances"][0])
        ]

    def all_hits(self) -> list[Hit]:
        res = self._col.get(include=["documents", "metadatas"])
        return [Hit(i, d, m) for i, d, m in zip(res["ids"], res["documents"], res["metadatas"])]

    def count(self) -> int:
        return self._col.count()
