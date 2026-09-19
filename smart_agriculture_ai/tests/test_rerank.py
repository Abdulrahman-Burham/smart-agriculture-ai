"""Tests for reranking logic."""

from smart_agriculture_ai.rag.rerank import metadata_filters, rerank_candidates


def test_metadata_filters():
    candidates = [
        {"id": "c1", "score": 0.9, "metadata": {"crop_type": "tomato", "disease_name": "blight", "region": "delta"}},
        {"id": "c2", "score": 0.7, "metadata": {"crop_type": "wheat", "disease_name": "rust", "region": "upper_egypt"}},
    ]
    result = metadata_filters(candidates, crop="tomato")
    assert len(result) == 1
    assert result[0]["id"] == "c1"


def test_rerank_candidates():
    candidates = [{"id": "c1", "score": 0.9}, {"id": "c2", "score": 0.7}]
    result = rerank_candidates(candidates, top_k=1)
    assert len(result) == 1
    assert result[0]["id"] == "c1"
