"""Prompt construction and grounded answer generation for the RAG assistant."""

from __future__ import annotations

from typing import Any


def build_prompt(query: str, context_chunks: list[dict[str, Any]]) -> str:
    """Build a grounded prompt instructing the model to answer only from context."""

    context_text = "\n\n---\n\n".join(
        f"[Chunk {idx + 1}] {chunk.get('content', '')}"
        for idx, chunk in enumerate(context_chunks)
    )

    prompt = f"""
    أنت مساعد زراعي عربي مصري. أجب فقط بناءً على السياق التالي.
    لا تستخدم معلومات خارجية أو خبرة شخصية.
    أجب باللغة العربية الزراعية المصرية.
    إذا كانت الإجابة تعتمد على توصيات علاج أو جرعات، قم بعلامتها كـ "يتطلب مراجعة زراعي/خبراء" دون تقديم وصفة علاجية مستقلة.
    أدرج الاستشهادات من المقاطع المدعمة في شكل [Chunk N].

    السؤال: {query}

    السياق:
    {context_text}
    """
    return prompt.strip()


def generate_answer(query: str, context_chunks: list[dict[str, Any]], llm_client) -> dict[str, Any]:
    """Generate a grounded answer from the top retrieved chunks."""

    prompt = build_prompt(query, context_chunks)
    answer_text = llm_client.generate_text(prompt) if llm_client is not None else "No LLM client configured."
    citations = [f"Chunk {idx + 1}" for idx in range(len(context_chunks))]
    retrieval_confidence = sum(float(chunk.get("score", 0.0)) for chunk in context_chunks) / max(1, len(context_chunks))
    needs_agronomist_review = retrieval_confidence < 0.35

    return {
        "answer": answer_text,
        "citations": citations,
        "retrieval_confidence": retrieval_confidence,
        "needs_agronomist_review": needs_agronomist_review,
    }
