"""Tests for retrieval behavior."""

from rag.retrieve import _rrf_score, hybrid_retrieval


def test_rrf_score():
    list_a = [{"id": "a1", "score": 1.0}, {"id": "a2", "score": 0.7}]
    list_b = [{"id": "a2", "score": 0.9}, {"id": "a1", "score": 0.8}]
    result = _rrf_score([list_a, list_b], k=60)
    assert len(result) >= 2
    assert result[0]["id"] in {"a1", "a2"}


def test_hybrid_retrieval_shape():
    class FakeVectorStore:
        def similarity_search(self, query, k=20, filters=None):
            return [{"id": "v1", "content": "Tomato disease guidance", "metadata": {"crop_type": "tomato", "disease_name": "blight"}}]

    class FakeBM25Index:
        def search(self, query, k=20):
            return [{"doc_id": "b1", "score": 0.8, "text": "Tomato blight treatment guidance"}]

    result = hybrid_retrieval("مرض الطماطم", FakeVectorStore(), FakeBM25Index(), "BAAI/bge-m3", intent="disease_query", top_k=5)
    assert len(result) >= 1
