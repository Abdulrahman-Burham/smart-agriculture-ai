"""BM25 index wrapper for sparse retrieval."""

from __future__ import annotations

from typing import Any

from rank_bm25 import BM25Okapi


class BM25Service:
    """Small wrapper around a BM25 index for search over chunk text."""

    def __init__(self, corpus: list[str] | None = None):
        self.corpus = corpus or []
        self.index = None
        self._tokenized = []
        if self.corpus:
            self._tokenized = [doc.lower().split() for doc in self.corpus]
            self.index = BM25Okapi(self._tokenized)

    def build_index(self, corpus: list[str]) -> "BM25Service":
        """Build a BM25 index from a text corpus."""

        self.corpus = corpus
        self._tokenized = [doc.lower().split() for doc in corpus]
        self.index = BM25Okapi(self._tokenized)
        return self

    def search(self, query: str, k: int = 20) -> list[dict[str, Any]]:
        """Return BM25-ranked search results for the query."""

        if self.index is None:
            return []

        tokens = query.lower().split()
        scores = self.index.get_scores(tokens)
        ranked = sorted(enumerate(scores), key=lambda item: item[1], reverse=True)[:k]
        return [
            {"doc_id": idx, "score": float(score), "text": self.corpus[idx]}
            for idx, score in ranked
        ]


def build_bm25_service(corpus: list[str] | None = None) -> BM25Service:
    """Factory helper."""

    return BM25Service(corpus=corpus)
