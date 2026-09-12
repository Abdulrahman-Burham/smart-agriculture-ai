"""Vector store wrapper with a Chroma-first design and a Pinecone-ready interface."""

from __future__ import annotations

from typing import Any, Iterable


class VectorStoreService:
    """Simple vector-store abstraction with Chroma-compatible methods."""

    def __init__(self, collection_name: str = "agriculture_kb", host: str | None = None):
        self.collection_name = collection_name
        self.host = host
        self._docs: list[dict[str, Any]] = []

    def add_documents(self, documents: list[dict[str, Any]]) -> list[str]:
        """Add documents to the in-memory collection for tests and local dev."""

        for doc in documents:
            doc.setdefault("id", f"doc-{len(self._docs) + 1}")
            self._docs.append(doc)
        return [doc["id"] for doc in documents]

    def similarity_search(self, query: str, k: int = 5, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Return a small mock result set. This is deliberately lightweight for scaffolding."""

        items = self._docs[:k]
        if filters:
            items = [
                item for item in items
                if all(item.get("metadata", {}).get(key) == value for key, value in filters.items())
            ]
        return [{"id": item.get("id"), "content": item.get("content", ""), "metadata": item.get("metadata", {})} for item in items]

    def get_collection(self) -> list[dict[str, Any]]:
        """Return the current in-memory collection."""

        return self._docs


def build_vector_store_service(collection_name: str = "agriculture_kb", host: str | None = None) -> VectorStoreService:
    """Factory helper."""

    return VectorStoreService(collection_name=collection_name, host=host)
