"""Tests for final response gating."""

from smart_agriculture_ai.rag.respond import evaluate_confidence, produce_response


class FakeLLM:
    def generate_text(self, prompt: str) -> str:
        return "محتوى من السياق"


def test_evaluate_confidence():
    assert evaluate_confidence([{"score": 0.4}, {"score": 0.5}], threshold=0.35) is True
    assert evaluate_confidence([{"score": 0.1}, {"score": 0.2}], threshold=0.35) is False


def test_produce_response():
    result = produce_response("سؤال", [{"id": "t1", "content": "محتوى", "score": 0.4}], FakeLLM(), threshold=0.35)
    assert "needs_agronomist_review" in result
    assert "answer" in result
