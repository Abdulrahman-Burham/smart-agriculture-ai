"""Grounded answer generation and provider-agnostic LLM interface module."""

from __future__ import annotations

import abc
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class LLMProviderInterface(abc.ABC):
    """Thin provider-agnostic interface for LLMs (OpenAI, HuggingFace, local, or Mock)."""

    @abc.abstractmethod
    def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Generate text completion from prompt."""
        pass


class MockLLMProvider(LLMProviderInterface):
    """Deterministic Mock LLM Provider for local execution and testing."""

    def __init__(self, default_response: Optional[str] = None):
        self.default_response = default_response

    def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        if self.default_response:
            return self.default_response

        # Grounded dummy Egyptian Arabic answer based on context
        if "لفحة" in prompt or "ندوة" in prompt:
            return (
                "بناءً على التوصيات المتاحة [مصدر 1]: يجب رش المبيد النحاسي أو المادتين الفعالتين (مانكوزيب + ميتالاكسيل) "
                "عند ظهور أولى علامات الإصابة باللفحة، مع تقليل مياه الري وتجنب الري بالرش فوق الأشجار/الأوراق. "
                "ملاحظة: هذه الإجابة تتطلب مراجعة المهندس الزراعي قبل التطبيق الميداني."
            )
        elif "تسميد" in prompt or "npk" in prompt.lower():
            return (
                "حسب دليل التسميد [مصدر 1]: يُوصى بإضافة سماد NPK المتوازن بنسبة 20-20-20 بمعدل 2-3 كجم للفدان "
                "مع مياه الري في الصباح الباكر، وإضافة السماد البلدي العضوي في بداية الموسم."
            )
        else:
            return (
                "وفقاً للكتيبات الزراعية المرفقة [مصدر 1]: يجب مراعاة انتظام مواعيد الري والتهوية الخفيفة للتربة "
                "لمنع انتشار الآفات والعفن."
            )


class OpenAILLMProvider(LLMProviderInterface):
    """OpenAI API wrapper implementation."""

    def __init__(
        self,
        api_key: str,
        model_name: str = "gpt-3.5-turbo",
        base_url: Optional[str] = None,
    ):
        self.api_key = api_key
        self.model_name = model_name
        self.base_url = base_url

    def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        try:
            import openai

            client = openai.OpenAI(api_key=self.api_key, base_url=self.base_url)
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            response = client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=0.1,
            )
            return response.choices[0].message.content or ""
        except Exception as err:
            logger.error(f"OpenAILLMProvider error: {err}")
            return f"Error executing OpenAI LLM query: {err}"


def build_grounded_prompt(query: str, context_chunks: List[Dict[str, Any]]) -> tuple[str, str]:
    """Assemble strict grounded prompt requiring Egyptian farming Arabic and chunk citations."""
    system_prompt = (
        "أنت خبير ومساعد زراعي مصري متخصص في خدمة المزارعين.\n"
        "تعليمات صارمة:\n"
        "1. أجب فقط بناءً على المعلومات الواردة في السياق المرفق أدناه.\n"
        "2. اكتب الإجابة باللهجة الزراعية المصرية الفصحى المفهومة للمزارع المصري.\n"
        "3. استشهد بوضوح بالمعلومات باستخدام [مصدر 1]، [مصدر 2]... حسب رقم المقطع.\n"
        "4. لا تُقدم أي توصية علاجية حاسمة أو وصفة مبيدات مستقلة دون النص على ضرورة مراجعة المرشد/المهندس الزراعي المختص.\n"
        "5. إذا لم تحتوِ المقاطع على معلومات كافية للإجابة، صرّح بوضوح: 'المعلومات المتاحة غير كافية'."
    )

    formatted_context = []
    for idx, chunk in enumerate(context_chunks, start=1):
        content = chunk.get("content", "").strip()
        meta = chunk.get("metadata", {})
        crop = meta.get("crop_type", "عام")
        disease = meta.get("disease_name", "عام")
        doc_type = meta.get("doc_type", "دليل")
        formatted_context.append(
            f"[مصدر {idx}] (المحصول: {crop} | المرض: {disease} | النوع: {doc_type}):\n{content}"
        )

    context_str = "\n\n---\n\n".join(formatted_context)

    user_prompt = (
        f"السؤال المطروح من المزارع:\n{query}\n\n"
        f"السياق الزراعي المعتمد:\n{context_str}\n\n"
        f"الإجابة المباشرة والاستشهادات:"
    )

    return system_prompt, user_prompt


def calculate_retrieval_confidence(context_chunks: List[Dict[str, Any]]) -> float:
    """Calculate normalized retrieval confidence score (0.0 to 1.0) from context candidates."""
    if not context_chunks:
        return 0.0

    scores = []
    for chunk in context_chunks:
        # Check available scores (rrf_score, vector_score, bm25_score)
        score = chunk.get("rrf_score")
        if score is None:
            score = chunk.get("vector_score")
        if score is None:
            score = chunk.get("bm25_score")
        if score is not None:
            scores.append(float(score))

    if not scores:
        return 0.5

    avg_score = sum(scores) / len(scores)

    # Normalize bounded score (RRF scores with k=60 & weights 0.5 usually fall between 0.01 and 0.04)
    # Scaled to range [0.0, 1.0] for confidence threshold comparison
    confidence = min(1.0, max(0.0, avg_score * 35.0))
    return round(confidence, 4)


def generate_grounded_answer(
    query: str,
    context_chunks: List[Dict[str, Any]],
    llm_provider: LLMProviderInterface,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Generate grounded Egyptian Arabic answer using top retrieved chunks."""
    if not context_chunks:
        return {
            "answer": "المعلومات المتاحة في قاعدة المعرفة الزراعية غير كافية للإجابة على سؤالك.",
            "citations": [],
            "retrieval_confidence": 0.0,
            "used_chunks_count": 0,
        }

    system_prompt, user_prompt = build_grounded_prompt(query, context_chunks)
    answer_text = llm_provider.generate_text(user_prompt, system_prompt=system_prompt)

    citations = [
        {
            "citation_tag": f"[مصدر {idx}]",
            "chunk_id": chunk.get("chunk_id"),
            "source_doc": chunk.get("metadata", {}).get("source_doc"),
            "doc_type": chunk.get("metadata", {}).get("doc_type"),
        }
        for idx, chunk in enumerate(context_chunks, start=1)
    ]

    confidence = calculate_retrieval_confidence(context_chunks)

    return {
        "answer": answer_text,
        "citations": citations,
        "retrieval_confidence": confidence,
        "used_chunks_count": len(context_chunks),
    }
