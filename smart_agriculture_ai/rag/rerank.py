"""Reranking and metadata filtering for retrieved agriculture chunks."""

from __future__ import annotations

from typing import Any


def metadata_filters(candidates: list[dict[str, Any]], crop: str | None = None, disease: str | None = None, region: str | None = None) -> list[dict[str, Any]]:
    """Filter candidate chunks by crop, disease, and region metadata."""

    filtered = []
    for candidate in candidates:
        metadata = candidate.get("metadata", {})
        if crop and str(metadata.get("crop_type", "")).lower() != crop.lower():
            continue
        if disease and str(metadata.get("disease_name", "")).lower() != disease.lower():
            continue
        if region and str(metadata.get("region", "")).lower() != region.lower():
            continue
        filtered.append(candidate)
    return filtered


def rerank_candidates(candidates: list[dict[str, Any]], top_k: int = 5) -> list[dict[str, Any]]:
    """Simple reranking over candidates before final context assembly."""

    ranked = sorted(candidates, key=lambda item: float(item.get("score", 0.0)), reverse=True)
    return ranked[:top_k]
