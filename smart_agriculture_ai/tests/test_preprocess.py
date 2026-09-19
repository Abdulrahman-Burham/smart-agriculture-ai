"""Tests for the preprocessing module."""

from smart_agriculture_ai.rag.preprocess import (
    canonicalize_terms,
    detect_query_intent,
    normalize_arabic_text,
    preprocess_query,
)


def test_normalize_arabic_text():
    raw = "أعطيني جرعة نبتة أأأ"
    result = normalize_arabic_text(raw)
    assert "ا" in result
    assert "أ" not in result


def test_canonicalize_terms():
    lexicon = {
        "dialect_aliases": {"سماد": ["سماد", "اسمدة", "اسمده"]},
        "product_aliases": {"npk": ["NPK", "ان بي كي"]},
    }
    out = canonicalize_terms("اسمدة NPK", lexicon)
    assert "سماد" in out.lower() or "npk" in out.lower()


def test_detect_query_intent():
    assert detect_query_intent("مرض في الطماطم") == "disease_query"
    assert detect_query_intent("كم جرعة سماد") == "dosage_lookup"


def test_preprocess_query():
    result = preprocess_query("مرض طماطم واسماد", {"dialect_aliases": {"مرض": ["مرض"]}, "product_aliases": {}})
    assert result["intent"] in {"disease_query", "general_advice"}
    assert result["original_query"] == "مرض طماطم واسماد"
