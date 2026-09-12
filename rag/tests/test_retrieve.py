"""Unit tests for rag/retrieve.py."""

from __future__ import annotations

import pytest

from rag.retrieve import (
    ChromaVectorStore,
    apply_vision_metadata_boost,
    calculate_rrf_score,
    get_intent_weights,
    hybrid_retrieval,
)


def test_rrf_fusion_math():
    dense_results = [
        {"chunk_id": "doc_A", "content": "Content A", "vector_score": 0.95},
        {"chunk_id": "doc_B", "content": "Content B", "vector_score": 0.85},
    ]

    sparse_results = [
        {"chunk_id": "doc_B", "content": "Content B", "bm25_score": 4.5},
        {"chunk_id": "doc_C", "content": "Content C", "bm25_score": 3.2},
    ]

    k = 60
    w_dense = 0.5
    w_sparse = 0.5

    fused = calculate_rrf_score(dense_results, sparse_results, k=k, w_dense=w_dense, w_sparse=w_sparse)

    # doc_B appears in rank 2 of dense and rank 1 of sparse
    # doc_B RRF score = 0.5 / (60 + 2) + 0.5 / (60 + 1) = (0.5/62) + (0.5/61)
    expected_doc_b_score = (0.5 / 62.0) + (0.5 / 61.0)

    # doc_A appears only in rank 1 of dense
    expected_doc_a_score = 0.5 / 61.0

    doc_b_entry = next(x for x in fused if x["chunk_id"] == "doc_B")
    doc_a_entry = next(x for x in fused if x["chunk_id"] == "doc_A")

    assert pytest.approx(doc_b_entry["rrf_score"], rel=1e-4) == expected_doc_b_score
    assert pytest.approx(doc_a_entry["rrf_score"], rel=1e-4) == expected_doc_a_score

    # doc_B should rank highest overall because it appeared in both dense and sparse top ranks
    assert fused[0]["chunk_id"] == "doc_B"


def test_intent_weights_bias():
    # Dosage lookup -> BM25 weight biased higher
    w_dense, w_sparse = get_intent_weights("dosage_lookup", "كمية NPK")
    assert w_sparse > w_dense
    assert w_sparse == 0.7
    assert w_dense == 0.3

    # General advice -> Vector weight biased higher
    w_dense_gen, w_sparse_gen = get_intent_weights("general_advice", "كيف أحافظ على محصوبي")
    assert w_dense_gen > w_sparse_gen
    assert w_dense_gen == 0.7
    assert w_sparse_gen == 0.3


def test_vision_metadata_boost():
    candidates = [
        {"chunk_id": "chunk_1", "metadata": {"crop_type": "tomato", "disease_name": "late_blight"}, "rrf_score": 0.02},
        {"chunk_id": "chunk_2", "metadata": {"crop_type": "wheat", "disease_name": "rust"}, "rrf_score": 0.02},
    ]

    vision_context = {
        "crop_type": "tomato",
        "disease_label": "late_blight",
        "confidence_score": 0.95,
    }

    boosted = apply_vision_metadata_boost(candidates, vision_context)

    # chunk_1 matching crop and disease should have higher score than chunk_2
    assert boosted[0]["chunk_id"] == "chunk_1"
    assert boosted[0]["rrf_score"] > boosted[1]["rrf_score"]


def test_hybrid_retrieval_end_to_end():
    vector_store = ChromaVectorStore()
    vector_store.add_documents([
        {
            "chunk_id": "c1",
            "content": "علاج اللفحة المتأخرة في الطماطم باستخدام المبيد النحاسي",
            "metadata": {"crop_type": "tomato", "disease_name": "late_blight"},
        }
    ])

    bm25_data = {
        "bm25_index": None,
        "corpus_chunks": [],
    }

    results = hybrid_retrieval("اللفحة المتأخرة الطماطم", vector_store, bm25_data, intent="disease_query")
    assert len(results) > 0
    assert results[0]["chunk_id"] == "c1"
