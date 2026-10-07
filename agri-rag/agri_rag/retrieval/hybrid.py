"""Hybrid retrieval: dense (Chroma) + lexical (BM25) fused with Reciprocal Rank Fusion.

Why hybrid: dense vectors capture meaning ("الورق بيصفر" ~ "اصفرار الأوراق"), BM25 captures exact
agronomic terms, numbers and product names that embeddings blur. RRF fuses the two rankings
without needing to calibrate their score scales.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field

from rank_bm25 import BM25Okapi

from ..config import Settings
from ..nlp.arabic import tokenize
from ..nlp.glossary import Glossary
from .embeddings import Embedder
from .vectorstore import GENERAL_CROP, ChromaStore, Hit


@dataclass
class RetrievedChunk:
    chunk_id: str
    text: str
    metadata: dict
    score: float  # fused RRF score
    similarity: float | None = None  # dense cosine similarity when available


@dataclass
class RetrievalResult:
    chunks: list[RetrievedChunk]
    expanded_query: str
    glossary_matches: list[tuple[str, str]] = field(default_factory=list)

    @property
    def top_similarity(self) -> float:
        return max((c.similarity or 0.0 for c in self.chunks), default=0.0)


class HybridRetriever:
    def __init__(self, store: ChromaStore, embedder: Embedder, glossary: Glossary, settings: Settings):
        self.store, self.embedder, self.glossary, self.s = store, embedder, glossary, settings
        self._lock = threading.Lock()
        self._hits: list[Hit] = []
        self._bm25: BM25Okapi | None = None
        self.refresh()

    def refresh(self) -> None:
        """Rebuild the in-memory BM25 index. Call after every (re)indexing."""
        hits = self.store.all_hits()
        bm25 = BM25Okapi([tokenize(h.text) or ["_"] for h in hits]) if hits else None
        with self._lock:
            self._hits, self._bm25 = hits, bm25

    def _lexical(self, query: str, n: int, crop: str | None) -> list[Hit]:
        with self._lock:
            hits, bm25 = self._hits, self._bm25
        tokens = tokenize(query)
        if not bm25 or not tokens:
            return []
        scores = bm25.get_scores(tokens)
        ranked = sorted(range(len(hits)), key=lambda i: scores[i], reverse=True)
        out: list[Hit] = []
        for i in ranked:
            if scores[i] <= 0:
                break
            if crop and crop != GENERAL_CROP and hits[i].metadata.get("crop") not in (crop, GENERAL_CROP):
                continue
            out.append(hits[i])
            if len(out) >= n:
                break
        return out

    def retrieve(self, query: str, crop: str | None = None, top_k: int | None = None) -> RetrievalResult:
        k = top_k or self.s.top_k
        crop = self.glossary.canonicalize(crop, "crop")
        expansion = self.glossary.expand(query)
        dense = self.store.query(self.embedder.embed_query(expansion.expanded), self.s.candidate_k, crop)
        lexical = self._lexical(expansion.expanded, self.s.candidate_k, crop)

        fused: dict[str, RetrievedChunk] = {}
        for ranking in (dense, lexical):
            for rank, hit in enumerate(ranking):
                item = fused.setdefault(hit.chunk_id, RetrievedChunk(hit.chunk_id, hit.text, hit.metadata, 0.0))
                item.score += 1.0 / (self.s.rrf_k + rank + 1)
                if hit.similarity is not None:
                    item.similarity = hit.similarity
        ordered = sorted(fused.values(), key=lambda c: c.score, reverse=True)[:k]
        return RetrievalResult(ordered, expansion.expanded, expansion.matches)
