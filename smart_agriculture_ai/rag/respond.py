"""Response assembly and confidence gating for the agricultural RAG assistant."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from rag.generate import generate_answer


def evaluate_confidence(top_candidates: list[dict[str, Any]], threshold: float = 0.35) -> bool:
    """Return whether the top retrieval scores are above the configured threshold."""

    if not top_candidates:
        return False
    average_score = sum(float(item.get("score", 0.0)) for item in top_candidates) / len(top_candidates)
    return average_score >= threshold


def log_response(request: dict[str, Any]) -> None:
    """Persist response metadata for evaluation and triage."""

    log_dir = Path(__file__).resolve().parents[1]
    log_path = log_dir / "response_log.jsonl"
    log_dir.mkdir(parents=True, exist_ok=True)

    with open(log_path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps({"timestamp": datetime.utcnow().isoformat(), **request}, ensure_ascii=False) + "\n")


def produce_response(query: str, context_chunks: list[dict[str, Any]], llm_client, threshold: float = 0.35) -> dict[str, Any]:
    """Assemble the final answer and flag when confidence is too low."""

    generated = generate_answer(query, context_chunks, llm_client)
    retrieval_confidence = float(generated.get("retrieval_confidence", 0.0))
    needs_agronomist_review = retrieval_confidence < threshold or generated.get("needs_agronomist_review", False)

    payload = {
        "query": query,
        "retrieved_chunk_ids": [chunk.get("id", "unknown") for chunk in context_chunks],
        "answer": generated.get("answer", ""),
        "confidence": retrieval_confidence,
        "needs_agronomist_review": needs_agronomist_review,
        "citations": generated.get("citations", []),
    }

    log_response(payload)
    return payload
