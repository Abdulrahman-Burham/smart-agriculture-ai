"""Reranking and metadata filtering module for retrieved chunk candidates."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def apply_metadata_filters(
    candidates: List[Dict[str, Any]],
    crop: Optional[str] = None,
    disease: Optional[str] = None,
    region: Optional[str] = None,
    strict: bool = False,
) -> List[Dict[str, Any]]:
    """Filter candidates based on crop, disease, or region metadata.

    If strict=False and filtering removes all candidates, falls back to original list.
    """
    if not candidates:
        return []

    filtered: List[Dict[str, Any]] = []

    for cand in candidates:
        meta = cand.get("metadata", {})
        cand_crop = str(meta.get("crop_type", "")).lower()
        cand_disease = str(meta.get("disease_name", "")).lower()
        cand_region = str(meta.get("region", "")).lower()

        if crop and cand_crop not in ["unknown", "general", "all"] and cand_crop != crop.lower():
            continue
        if disease and cand_disease not in ["unknown", "general", "all"] and cand_disease != disease.lower():
            continue
        if region and cand_region not in ["unknown", "general", "egypt_general"] and cand_region != region.lower():
            continue

        filtered.append(cand)

    if not filtered and not strict:
        logger.info("Metadata filtering returned empty list; falling back to original candidates.")
        return candidates

    return filtered


def rerank_candidates(
    candidates: List[Dict[str, Any]],
    query: str,
    top_k: int = 5,
    use_cross_encoder: bool = False,
    config: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Rerank candidates to top_k using fusion score order or optional cross-encoder model."""
    if not candidates:
        return []

    if use_cross_encoder:
        try:
            from sentence_transformers import CrossEncoder

            model_name = "BAAI/bge-reranker-base"
            encoder = CrossEncoder(model_name)
            pairs = [(query, cand["content"]) for cand in candidates]
            scores = encoder.predict(pairs)

            for cand, score in zip(candidates, scores):
                cand["rerank_score"] = float(score)

            reranked = sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)
            return reranked[:top_k]
        except Exception as err:
            logger.warning(f"Cross-encoder reranking failed ({err}). Falling back to fusion rank order.")

    # Standard passthrough using RRF / fusion score order
    candidates_sorted = sorted(candidates, key=lambda x: x.get("rrf_score", 0.0), reverse=True)
    return candidates_sorted[:top_k]
