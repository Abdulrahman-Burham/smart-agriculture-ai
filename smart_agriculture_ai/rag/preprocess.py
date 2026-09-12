"""Preprocessing utilities for Arabic agricultural query normalization."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


ARABIC_DIACRITICS = "\u064B\u064C\u064D\u064E\u064F\u0650\u0651\u0652\u0653\u0654\u0655\u0656\u0657\u0658\u0670\u06E1\u06E2\u06E3\u06E4\u06E5\u06E6\u06E7\u06E8\u06E9"


def normalize_arabic_text(text: str) -> str:
    """Normalize common Arabic typing variants and orthographic inconsistencies."""

    if not text:
        return ""

    normalized = text
    normalized = normalized.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    normalized = normalized.replace("ى", "ي")
    normalized = re.sub(r"ة(?=\b|\s|[،.?!:;])", "ه", normalized)
    normalized = re.sub(f"[{ARABIC_DIACRITICS}]", "", normalized)
    normalized = re.sub(r"(.)\1{2,}", r"\1\1", normalized)
    normalized = normalized.strip()
    return normalized


def load_lexicon(path: str) -> dict[str, Any]:
    """Load the lexicon JSON used for canonicalization and alias expansion."""

    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def canonicalize_terms(text: str, lexicon: dict[str, Any]) -> str:
    """Apply dialect and product aliases to standardize agricultural terminology."""

    cleaned = normalize_arabic_text(text)
    if not lexicon:
        return cleaned

    replacements: list[tuple[str, str]] = []

    alias_map: dict[str, str] = {}
    for group_name, entries in lexicon.get("dialect_aliases", {}).items():
        for item in entries:
            alias_map[item.lower()] = group_name.lower()
    for group_name, entries in lexicon.get("product_aliases", {}).items():
        for item in entries:
            alias_map[item.lower()] = group_name.lower()

    for key, value in sorted(alias_map.items(), key=lambda x: len(x[0]), reverse=True):
        pattern = re.compile(re.escape(key), re.IGNORECASE)
        cleaned = pattern.sub(value, cleaned)

    return cleaned


def detect_query_intent(query: str) -> str:
    """Detect a coarse query intent for retrieval routing."""

    normalized = normalize_arabic_text((query or "").lower())
    if any(word in normalized for word in ["مرض", "لفحة", "صدأ", "عفن", "ذبول", "آفة", "حشرة", "بكتيريا"]):
        return "disease_query"
    if any(pattern in normalized for pattern in ["جرعة", "كمية", "جرعات", "نسبة", "معدل", "تسميد", "سماد", "مبيد"]):
        return "dosage_lookup"
    if any(word in normalized for word in ["ري", "مياه", "معدل الري", "متي", "توقيت الري", "رطوبة", "سقاية"]):
        return "general_advice"
    return "general_advice"


def preprocess_query(query: str, lexicon: dict[str, Any], vision_context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Normalize and enrich a user query before retrieval."""

    original = query or ""
    cleaned = normalize_arabic_text(original)
    canonical = canonicalize_terms(cleaned, lexicon)
    intent = detect_query_intent(canonical)

    metadata: dict[str, Any] = {
        "lang": "ar",
        "intent": intent,
        "normalized": True,
    }

    if vision_context:
        metadata["vision_context"] = vision_context

    return {
        "original_query": original,
        "cleaned_query": cleaned,
        "canonical_query": canonical,
        "intent": intent,
        "vision_context": vision_context,
        "metadata": metadata,
    }


def fallback_llm_rewrite(query: str) -> str:
    """Stub for a cheap LLM rewrite step used when retrieval quality is poor."""

    if not query:
        return ""
    return f"{query.strip()}".replace("  ", " ")


def log_rewrite_fallback(query: str, rewritten_query: str) -> None:
    """Write fallback rewrite events for later lexicon review."""

    log_dir = Path(__file__).resolve().parents[1]
    log_path = log_dir / "fallback_rewrites.jsonl"
    log_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "query": query,
        "rewritten_query": rewritten_query,
    }

    with open(log_path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
