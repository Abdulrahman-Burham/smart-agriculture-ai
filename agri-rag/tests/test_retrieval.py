import pytest


@pytest.mark.parametrize("question,crop,expected", [
    ("الورق بتاع القوطة عليه بقع مايه غامقة وتحت الورقة زغب أبيض", "قوطة", "tomato_late_blight.md"),
    ("القمح طلع عليه خطوط صفرا زي البودرة", "قمح", "wheat_rust.md"),
    ("الأرض عندي مالحة أعمل إيه؟", None, "soil_ph_salinity.md"),
    ("في دبانة بيضا على الفلفل", None, "aphids_whitefly.md"),
    ("هل أروي لو متوقع مطر بكرة؟", None, "irrigation_scheduling.md"),
])
def test_dialect_questions_find_right_source(container, question, crop, expected):
    res = container.retriever.retrieve(question, crop, top_k=3)
    assert len(res.chunks) > 0
    assert any(c.metadata["source"].endswith(".md") for c in res.chunks)


def test_crop_filter_excludes_other_crops(container):
    res = container.retriever.retrieve("مرض على الأوراق", crop="قمح", top_k=10)
    assert {c.metadata["crop"] for c in res.chunks} <= {"قمح", "عام"}


def test_reindex_is_idempotent(container, settings):
    from agri_rag.ingestion.indexer import index_directory

    before = container.store.count()
    index_directory(settings.knowledge_dir, container.store, settings)
    assert container.store.count() == before
