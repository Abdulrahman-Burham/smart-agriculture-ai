"""Unit tests for rag/preprocess.py."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from rag.preprocess import (
    canonicalize_terms,
    detect_query_intent,
    log_fallback_query,
    normalize_arabic_text,
    preprocess_query,
)


def test_normalize_arabic_text():
    # Test Alef unification (أ إ آ -> ا)
    assert normalize_arabic_text("أحمد إبراهيم آدام") == "احمد ابراهيم ادام"

    # Test Alef Maqsura (ى -> ي)
    assert normalize_arabic_text("علي ورامي والري") == "علي ورامي والري"

    # Test Taa Marbouta at word boundary (ة -> ه)
    assert normalize_arabic_text("ندوة متاخرة في الطماطم") == "ندوه متاخره في الطماطم"

    # Test diacritics removal
    assert normalize_arabic_text("الْمُبِيدَاتُ الزِّرَاعِيَّةُ") == "المبيدات الزراعيه"

    # Test character deduplication (3+ chars -> 2 chars)
    assert normalize_arabic_text("سلاااااام") == "سلاام"


def test_lexicon_substitution():
    lexicon = {
        "dialect_aliases": {
            "لفحة متاخرة": ["ندوة", "الندوة", "ندوة متاخرة"],
            "بياض دقيقي": ["بياض", "البياض"],
            "كبريت زراعي": ["عفار"],
        },
        "product_aliases": {
            "سماد مركبي NPK": ["npk", "الـ npk"],
            "سماد اليوريا 46%": ["urea", "يوريا"],
        },
    }

    # Test dialect replacement
    canonical = canonicalize_terms("عندي ندوة في محصول الطماطم وعايز عفار", lexicon)
    assert "لفحة متاخرة" in canonical
    assert "كبريت زراعي" in canonical

    # Test code-switched product replacement
    canonical_npk = canonicalize_terms("ما هي جرعة الـ NPK للقمح؟", lexicon)
    assert "سماد مركبي NPK" in canonical_npk


def test_detect_query_intent():
    assert detect_query_intent("ما هو علاج أعراض مرض اللفحة المتأخرة في البطاطس؟") == "disease_query"
    assert detect_query_intent("ما هي جرعة سماد اليوريا لكل فدان؟") == "dosage_lookup"
    assert detect_query_intent("متى يفضل ري القمح في موسم الشتاء؟") == "general_advice"


def test_preprocess_query_structure():
    lexicon = {"dialect_aliases": {}, "product_aliases": {}}
    vision_context = {"crop_type": "tomato", "disease_label": "late_blight", "confidence_score": 0.92}

    res = preprocess_query("طريقة ري الطماطم", lexicon, vision_context=vision_context)
    assert "original_query" in res
    assert "normalized_query" in res
    assert "canonical_query" in res
    assert "intent" in res
    assert res["vision_context"]["crop_type"] == "tomato"


def test_log_fallback_query(tmp_path):
    log_file = tmp_path / "logs" / "fallback.jsonl"
    log_fallback_query("عايز دواء للندوة", "علاج اللفحة المتأخرة", log_path=log_file)

    assert log_file.exists()
    lines = log_file.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["original_query"] == "عايز دواء للندوة"
    assert data["rewritten_query"] == "علاج اللفحة المتأخرة"
