"""Unit tests for rag/generate.py and confidence-flag branching."""

from __future__ import annotations

import pytest

from rag.generate import (
    MockLLMProvider,
    build_grounded_prompt,
    calculate_retrieval_confidence,
    generate_grounded_answer,
)
from rag.respond import RAGPipeline


def test_build_grounded_prompt():
    chunks = [
        {
            "chunk_id": "chk_1",
            "content": "يتم رش مبيد مانكوزيب بمعدل 250 جم لكل 100 لتر ماء.",
            "metadata": {"crop_type": "بطاطس", "disease_name": "لفحة متاخرة", "doc_type": "protocol"},
        }
    ]

    system_prompt, user_prompt = build_grounded_prompt("ما هي جرعة رش المبيد؟", chunks)

    assert "اللهجة الزراعية المصرية" in system_prompt
    assert "استشهد بوضوح" in system_prompt
    assert "[مصدر 1]" in user_prompt
    assert "جرعة رش المبيد" in user_prompt


def test_calculate_retrieval_confidence():
    # Test confidence calculation with high scores
    high_score_chunks = [{"rrf_score": 0.035}, {"rrf_score": 0.030}]
    conf_high = calculate_retrieval_confidence(high_score_chunks)
    assert conf_high >= 0.70

    # Test confidence calculation with low scores
    low_score_chunks = [{"rrf_score": 0.002}]
    conf_low = calculate_retrieval_confidence(low_score_chunks)
    assert conf_low < 0.20

    # Test empty chunks
    assert calculate_retrieval_confidence([]) == 0.0


def test_generate_grounded_answer_mock():
    provider = MockLLMProvider()
    chunks = [
        {
            "chunk_id": "chk_1",
            "content": "يُوصى بالري المنتظم للقمح في بداية الصباح.",
            "metadata": {"crop_type": "قمح", "disease_name": "عام", "doc_type": "guide"},
            "rrf_score": 0.025,
        }
    ]

    res = generate_grounded_answer("كيف أروي القمح؟", chunks, provider)

    assert "answer" in res
    assert "citations" in res
    assert len(res["citations"]) == 1
    assert res["citations"][0]["citation_tag"] == "[مصدر 1]"
    assert res["retrieval_confidence"] > 0.0


def test_pipeline_confidence_flag_branching(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
confidence:
  threshold: 0.50
retrieval:
  top_k_fused: 5
  rrf_k: 60
rerank:
  top_k: 3
logging:
  requests_log: str(tmp_path / "requests.jsonl")
        """,
        encoding="utf-8",
    )

    pipeline = RAGPipeline(config_path=str(config_file))

    # Ingest document
    doc = {
        "content": "علاج مرض البياض الدقيقي في الخيار يكون باستخدام كبريت ميكروني 250جم/100لتر ماء.",
        "doc_type": "protocol",
        "crop_type": "cucumber",
        "disease_name": "powdery_mildew",
    }
    pipeline.ingest_documents([doc])

    # Run query
    response = pipeline.run("علاج البياض الدقيقي في الخيار")

    assert "answer" in response
    assert "needs_agronomist_review" in response
    assert "citations" in response
    assert "latency_seconds" in response
