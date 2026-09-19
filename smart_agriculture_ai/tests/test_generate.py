"""Tests for prompt building and answer generation."""

from smart_agriculture_ai.rag.generate import build_prompt, generate_answer


class FakeLLM:
    def generate_text(self, prompt: str) -> str:
        return "الإجابة تعتمد على السياق المتاح."


def test_build_prompt_contains_constraints():
    prompt = build_prompt("هل هذا مرض؟", [{"content": "context chunk"}])
    assert "أجب فقط بناءً على السياق التالي" in prompt
    assert "العربية الزراعية المصرية" in prompt


def test_generate_answer():
    result = generate_answer("هل يمكن العمل؟", [{"content": "محتوى", "score": 0.8}], FakeLLM())
    assert "answer" in result
    assert "retrieval_confidence" in result
    assert isinstance(result["citations"], list)
