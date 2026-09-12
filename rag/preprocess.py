"""Arabic orthography normalization, dialect canonicalization, and intent detection module."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Arabic diacritics unicode range (\u064B - \u0652, plus extra honorifics/tanween)
ARABIC_DIACRITICS = re.compile(r"[\u064B-\u0652\u0640\u0653-\u0655\u0670]")


def normalize_arabic_text(text: str) -> str:
    """Normalize common Arabic orthographic variations and remove diacritics.

    - Unifies Alef forms (أ, إ, آ -> ا)
    - Replaces Alef Maqsura with Yaa (ى -> ي)
    - Normalizes Taa Marbouta to Haa (ة -> ه) at word boundaries
    - Strips all diacritics and tatweel
    - Collapses repeated characters (3 or more consecutive -> 2)
    """
    if not text:
        return ""

    normalized = text

    # Strip diacritics and tatweel
    normalized = ARABIC_DIACRITICS.sub("", normalized)

    # Unify Alef forms
    normalized = normalized.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")

    # Replace Alef Maqsura with Yaa
    normalized = normalized.replace("ى", "ي")

    # Replace Taa Marbouta with Haa at word endings / before spaces/punctuation
    normalized = re.sub(r"ة(?=\b|\s|[،.?!:;]|$)", "ه", normalized)

    # Collapse repeated letters (3 or more down to 2)
    normalized = re.sub(r"(.)\1{2,}", r"\1\1", normalized)

    return normalized.strip()


def load_lexicon(path: str | Path) -> Dict[str, Any]:
    """Load dialect and product canonicalization dictionary from JSON file."""
    filepath = Path(path)
    if not filepath.exists():
        logger.warning(f"Lexicon file not found at {filepath}. Returning empty lexicon.")
        return {"dialect_aliases": {}, "product_aliases": {}}

    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def canonicalize_terms(text: str, lexicon: Dict[str, Any]) -> str:
    """Substitute dialect and code-switched terms with canonical agricultural Arabic terms."""
    if not text or not lexicon:
        return text

    normalized = normalize_arabic_text(text)

    # Build substitution map (term -> canonical term)
    substitutions: list[tuple[str, str]] = []

    # Dialect aliases: canonical_name -> list of alias terms
    for canonical, aliases in lexicon.get("dialect_aliases", {}).items():
        for alias in aliases:
            norm_alias = normalize_arabic_text(alias)
            substitutions.append((norm_alias, canonical))

    # Product aliases: canonical_name -> list of alias terms (including English NPK, Urea, etc.)
    for canonical, aliases in lexicon.get("product_aliases", {}).items():
        for alias in aliases:
            substitutions.append((alias.lower(), canonical))
            substitutions.append((normalize_arabic_text(alias), canonical))

    # Sort substitutions by descending length to prevent partial substring collisions
    substitutions.sort(key=lambda item: len(item[0]), reverse=True)

    result = normalized
    for alias_pattern, canonical_replacement in substitutions:
        if not alias_pattern:
            continue
        # Case insensitive boundary matching for English/Code-switched, simple replace for Arabic
        if re.search(r"[a-zA-Z]", alias_pattern):
            pattern = re.compile(r"\b" + re.escape(alias_pattern) + r"\b", re.IGNORECASE)
            result = pattern.sub(canonical_replacement, result)
        else:
            pattern = re.compile(re.escape(alias_pattern))
            result = pattern.sub(canonical_replacement, result)

    return result.strip()


def detect_query_intent(query: str) -> str:
    """Detect coarse query intent: 'disease_query', 'dosage_lookup', or 'general_advice'."""
    normalized = normalize_arabic_text((query or "").lower())

    # Dosage / pesticide / fertilizer lookup indicators
    dosage_keywords = [
        "جرعة", "جرعات", "كمية", "نسبة", "معدل", "تسميد", "سماد", "مبيد",
        "تركيز", "معاملة", "npk", "urea", "يوريا", "لتر", "فدان", "رش"
    ]
    if any(kw in normalized for kw in dosage_keywords):
        return "dosage_lookup"

    # Disease / pest identification indicators
    disease_keywords = [
        "مرض", "امراض", "اعراض", "اصابة", "عفن", "لفحة", "صدأ", "ذبول",
        "حشرة", "حشرات", "آفة", "آفات", "بكتيريا", "ديدان", "سوسة", "بياض"
    ]
    if any(kw in normalized for kw in disease_keywords):
        return "disease_query"

    return "general_advice"


def preprocess_query(
    query: str,
    lexicon: Dict[str, Any],
    vision_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Run full preprocessing pipeline on input query.

    Returns structured metadata including normalized query, canonical terms, intent,
    and vision context if provided.
    """
    raw_query = query or ""
    normalized = normalize_arabic_text(raw_query)
    canonical = canonicalize_terms(raw_query, lexicon)
    intent = detect_query_intent(canonical)

    metadata: Dict[str, Any] = {
        "intent": intent,
        "is_normalized": True,
        "has_lexicon_matches": canonical != normalized,
    }

    if vision_context:
        metadata["vision_context"] = vision_context

    return {
        "original_query": raw_query,
        "normalized_query": normalized,
        "canonical_query": canonical,
        "intent": intent,
        "metadata": metadata,
        "vision_context": vision_context,
    }


def fallback_llm_rewrite(query: str, llm_provider: Any = None) -> str:
    """Call a fast LLM to rewrite dialect query into standard agricultural Arabic."""
    if not query:
        return ""

    if llm_provider is not None and hasattr(llm_provider, "generate_text"):
        prompt = (
            f"اعد صياغة السؤال التالي باللهجة الزراعية الفصحى أو المعيارية للبحث الزراعي:\n"
            f"السؤال: {query}\n"
            f"الصياغة المعيارية:"
        )
        try:
            rewritten = llm_provider.generate_text(prompt)
            if rewritten and len(rewritten.strip()) > 0:
                return rewritten.strip()
        except Exception as err:
            logger.warning(f"LLM rewrite fallback failed: {err}")

    # Pure function fallback transformation if no LLM active
    cleaned = normalize_arabic_text(query)
    return f"تشخيص وعلاج {cleaned}"


def log_fallback_query(
    original_query: str,
    rewritten_query: str,
    log_path: str | Path = "logs/fallback_queries.jsonl",
) -> None:
    """Log original and rewritten query to JSONL for lexicon review."""
    filepath = Path(log_path)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "original_query": original_query,
        "rewritten_query": rewritten_query,
    }

    with open(filepath, "a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")
