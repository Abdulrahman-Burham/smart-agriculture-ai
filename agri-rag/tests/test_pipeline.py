import pytest

from agri_rag.domain.farm import FarmContext, SoilReport, VisionDiagnosis
from agri_rag.generation.prompts import FALLBACK_ANSWER


@pytest.mark.asyncio
async def test_answer_is_grounded_with_sources_and_citations(container):
    res = await container.pipeline.ask("الأرض مالحة أعمل إيه؟")
    assert res.grounded and res.sources and res.cited_ids == [1]
    assert res.timings["ttft_ms"] >= 0


@pytest.mark.asyncio
async def test_farm_context_reaches_prompt(container):
    farm = FarmContext(crop="طماطم", soil=SoilReport(ph=8.2, ec_ds_m=3.1),
                       diagnoses=[VisionDiagnosis(label="اللفحة المتأخرة", confidence=0.42)])
    await container.pipeline.ask("عندي مشكلة في الورق", farm=farm)
    prompt = container.llm.calls[-1]["messages"][-1]["content"]
    assert "pH=8.2" in prompt and "غير مؤكد" in prompt and "<sources>" in prompt


@pytest.mark.asyncio
async def test_below_similarity_gate_refuses_without_calling_llm(container):
    container.pipeline.s.min_similarity = 0.99
    res = await container.pipeline.ask("سعر الدولار النهاردة كام؟")
    assert not res.grounded and res.answer == FALLBACK_ANSWER
    assert container.llm.calls == []


@pytest.mark.asyncio
async def test_followup_uses_session_history(container):
    first = await container.pipeline.ask("الأرض مالحة أعمل إيه؟", session_id="s1")
    await container.pipeline.ask("وبعدين؟", session_id="s1")
    history = container.llm.calls[-1]["messages"]
    assert history[0]["content"] == "الأرض مالحة أعمل إيه؟" and first.session_id == "s1"


@pytest.mark.asyncio
async def test_vague_question_uses_confident_diagnosis_for_retrieval(container):
    farm = FarmContext(crop="طماطم", diagnoses=[VisionDiagnosis(label="اللفحة المتأخرة", confidence=0.88)])
    res = await container.pipeline.ask("عندي مشكلة في الورق", farm=farm)
    assert any("طماطم" in s["source"] or "tomato" in s["source"] for s in res.sources[:3])


@pytest.mark.asyncio
async def test_low_confidence_diagnosis_is_not_used_for_retrieval(container):
    farm = FarmContext(diagnoses=[VisionDiagnosis(label="الصدأ", confidence=0.30)])
    q = container.pipeline._retrieval_query("عندي مشكلة في الورق", [], farm)
    assert "الصدأ" not in q


@pytest.mark.parametrize("answer,expected", [
    ("حسب [1] و[3].", [1, 3]),
    ("كلام [1, 2] وكمان [2, farm_context]", [1, 2]),
    ("بيانات مزرعتك [farm_context] ومصدر وهمي [99]", []),
])
def test_citation_extraction_is_tolerant(answer, expected):
    from agri_rag.pipeline import extract_cited_ids

    assert extract_cited_ids(answer, 5) == expected
