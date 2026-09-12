"""Hybrid retrieval for the agricultural RAG pipeline."""

from __future__ import annotations

from typing import Any

from config.settings import get_settings


def _rrf_score(documents: list[dict[str, Any]], k: int = 60) -> list[dict[str, Any]]:
    """Fuse multiple ranked lists using reciprocal rank fusion."""

    rank_map: dict[str, float] = {}

    for ranked_list in documents:
        for rank, item in enumerate(ranked_list, start=1):
            doc_id = str(item.get("id") or item.get("doc_id") or item.get("metadata", {}).get("source_doc", f"doc-{rank}"))
            rank_map[doc_id] = rank_map.get(doc_id, 0.0) + (1.0 / (k + rank))

    fused = []
    for doc_id, score in rank_map.items():
        fused.append({"id": doc_id, "score": score})

    fused.sort(key=lambda item: item["score"], reverse=True)
    return fused


def _apply_vision_boost(candidates: list[dict[str, Any]], vision_context: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Boost candidate chunks matching crop/disease metadata when available."""

    if not vision_context:
        return candidates

    crop = (vision_context.get("crop_type") or "").lower()
    disease = (vision_context.get("disease_label") or "").lower()
    if not crop and not disease:
        return candidates

    boosted = []
    for candidate in candidates:
        metadata = candidate.get("metadata", {})
        match_score = 0.0
        if crop and str(metadata.get("crop_type", "")).lower() == crop:
            match_score += 0.3
        if disease and str(metadata.get("disease_name", "")).lower() == disease:
            match_score += 0.5
        candidate["score"] = float(candidate.get("score", 0.0)) + match_score
        boosted.append(candidate)
    boosted.sort(key=lambda item: item["score"], reverse=True)
    return boosted


def _detect_product_code_pattern(query: str) -> bool:
    """Flag NPK-style product names and similar code-switched dosage terms."""

    q = (query or "").lower()
    return any(token in q for token in ["npk", "n-p-k", "urea", "super phosphate", "fertilizer", "سماد", "مبيد", "يوريا"])


def hybrid_retrieval(
    query: str,
    vector_store,
    bm25_index,
    embedding_model,
    intent: str = "general_advice",
    vision_context: dict[str, Any] | None = None,
    top_k: int = 20,
    weights: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    """Run vector and BM25 retrieval in parallel conceptually and merge results via RRF."""

    settings = get_settings()
    weights = weights or settings.retrieval_weights

    vector_results: list[dict[str, Any]] = []
    if vector_store is not None:
        vector_results = vector_store.similarity_search(query, k=20)

    bm25_results: list[dict[str, Any]] = []
    if bm25_index is not None:
        bm25_results = bm25_index.search(query, k=20)

    vector_results = [{"id": item.get("id", "vector-doc"), "content": item.get("content", ""), "metadata": item.get("metadata", {}), "score": 1.0} for item in vector_results]
    bm25_results = [{"id": item.get("doc_id", f"bm25-{idx}"), "content": item.get("text", ""), "metadata": {}, "score": item.get("score", 0.0)} for idx, item in enumerate(bm25_results)]

    if intent == "dosage_lookup" or _detect_product_code_pattern(query):
        weights = {"vector": 0.4, "bm25": 0.6}

    if intent == "general_advice":
        weights = {"vector": 0.7, "bm25": 0.3}

    rrfs = [_rrf_score([vector_results]), _rrf_score([bm25_results])]
    merged = _rrf_score(rrfs, k=60)
    merged = _apply_vision_boost(merged, vision_context)

    for item in merged:
        item["score"] *= max(0.1, weights.get("vector", 0.5))
        if item.get("id", "").startswith("bm25") or any("bm25" in str(item.get("id")) for _ in [0]):
            item["score"] *= max(0.1, weights.get("bm25", 0.5))

    merged.sort(key=lambda item: item["score"], reverse=True)
    return merged[: max(1, min(top_k, 20))]
