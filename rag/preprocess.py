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

UNINTELLIGIBLE_RESPONSE = (
    "معلش يا غالي، الكلام اللي كتبته مش واضح ليا أو مش مفهوم بالظبط 🌾\n\n"
    "أنا هنا مهندسك وخبيرك الزراعي.. عشان أقدر أساعدك صح، ياريت تقولي:\n"
    "1. **إيه هو محصولك؟** (طماطم، بطاطس، قمح، مانجو، ذرة...)\n"
    "2. **إيه المشكلة أو السؤال اللي شاغلك؟** (اصفرار ورق، بقع، حشرات، مواعيد ري، أو تسميد...)\n\n"
    "📸 أو صوّر ورقة النبات بكاميرا الموبايل من زر الفحص فوق وهشخصهالك على طول!"
)

AMBIGUOUS_CLARIFICATION_RESPONSE = (
    "تحت أمرك يا باشا وجاهز أساعدك فوراً! بس عشان أديك الحل والعلاج المظبوط:\n\n"
    "🌱 **إيه نوع الزرعة أو المحصول اللي بتسأل عنه؟**\n"
    "🔍 **وإيه العرض أو المشكلة اللي لاحظتها في الأرض؟** (زي: نشفان ورق، تسقيط زهر، عفن، أو استفسار عن تسميد معين؟)\n\n"
    "اكتبلي التفاصيل البسيطة دي أو ارفع صورة للورقة، وهقولك تعمل إيه بالظبط خطوة بخطوة."
)


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
        logger.warning(
            f"Lexicon file not found at {filepath}. Returning empty lexicon."
        )
        return {"dialect_aliases": {}, "product_aliases": {}}

    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def canonicalize_terms(text: str, lexicon: Dict[str, Any]) -> str:
    """Substitute dialect and code-switched terms with canonical agricultural Arabic terms in a single pass."""
    if not text or not lexicon:
        return text

    normalized = normalize_arabic_text(text)

    # Build unique alias-to-canonical mapping
    alias_map: Dict[str, str] = {}

    for canonical, aliases in lexicon.get("dialect_aliases", {}).items():
        for alias in aliases:
            norm_alias = normalize_arabic_text(alias).strip()
            if norm_alias and norm_alias != canonical:
                alias_map[norm_alias.lower()] = canonical

    for canonical, aliases in lexicon.get("product_aliases", {}).items():
        for alias in aliases:
            norm_alias = normalize_arabic_text(alias).strip()
            if norm_alias and norm_alias != canonical:
                alias_map[norm_alias.lower()] = canonical

    if not alias_map:
        return normalized

    # Sort aliases by descending length so longer phrases match first (e.g. 'الـ npk' before 'npk')
    sorted_aliases = sorted(alias_map.keys(), key=len, reverse=True)

    # Build single-pass regex pattern
    pattern_parts = []
    for alias in sorted_aliases:
        escaped = re.escape(alias)
        if re.search(r"[a-zA-Z0-9]", alias):
            pattern_parts.append(r"(?<![a-zA-Z0-9])" + escaped + r"(?![a-zA-Z0-9])")
        else:
            pattern_parts.append(escaped)

    master_pattern = re.compile("|".join(pattern_parts), re.IGNORECASE)

    def _replace_match(match: re.Match) -> str:
        key = match.group(0).lower()
        return alias_map.get(key, alias_map.get(normalize_arabic_text(key).lower(), match.group(0)))

    result = master_pattern.sub(_replace_match, normalized)
    return result.strip()


def detect_query_intent(query: str, has_context: bool = False) -> str:
    """Detect coarse query intent with HCI-grounded verbosity and clarification routing.

    Returns:
    - 'unintelligible': gibberish, pure symbols, or random keyboard mash
    - 'needs_clarification': ambiguous queries without crop or symptom context
    - 'chit_chat': greetings, social pleasantries, and thank-you notes
    - 'quick_direct': binary questions, mixing checks, timing ('كلمتين ويسكت')
    - 'comprehensive_protocol': full fertilization/IPM schedules ('بروتوكول تفصيلي')
    - 'dosage_lookup': exact feddan / chemical dosages
    - 'disease_query': pest / pathogen diagnosis
    - 'general_advice': balanced agricultural advisory
    """
    raw = (query or "").strip()
    if not raw or len(raw) < 2:
        return "unintelligible"

    # 1. No letters exist (pure punctuation, symbols, or pure digits)
    if not re.search(r"[a-zA-Z\u0621-\u064A]", raw):
        return "unintelligible"

    # 2. Repeated single character 4+ times with tiny charset (e.g. "ءءءء", "aaaa")
    cleaned_chars = raw.replace(" ", "")
    if re.search(r"(.)\1{4,}", raw) and len(set(cleaned_chars)) <= 2:
        if set(cleaned_chars) == {"ه"}:
            return "chit_chat"
        return "unintelligible"

    # 3. Latin keyboard mash
    latin_chars = re.findall(r"[a-zA-Z]", raw)
    arabic_chars = re.findall(r"[\u0621-\u064A]", raw)
    if latin_chars and not arabic_chars:
        clean_lat = raw.lower().strip()
        common_en = {
            "hi",
            "hello",
            "thanks",
            "thank you",
            "ok",
            "yes",
            "no",
            "tomato",
            "potato",
            "npk",
            "urea",
            "wheat",
        }
        if clean_lat not in common_en and len(clean_lat) >= 4:
            vowels = sum(1 for c in clean_lat if c in "aeiou")
            if vowels == 0 or len(clean_lat) / max(vowels, 1) > 5:
                return "unintelligible"

    normalized = normalize_arabic_text(raw.lower())

    # 4. Extreme Ambiguity without Context (e.g. "اعمل ايه؟", "الحقني", "بايظة")
    vague_phrases = [
        "اعمل ايه",
        "الحقني",
        "بايظة",
        "بتموت",
        "عندي مشكلة",
        "ساعدني",
        "قولي اعمل ايه",
        "الحل ايه",
        "الزرعة تعبانة",
        "فيه مشكلة",
        "انقذني",
        "اسوي ايه",
    ]
    clean_punct = re.sub(r"[؟?!.،,:\-_\s]+", " ", normalized).strip()
    if not has_context and any(
        clean_punct == vp or clean_punct.startswith(vp + " ") for vp in vague_phrases
    ):
        return "needs_clarification"

    # 5. Chit-chat / Greetings indicators
    chit_chat_keywords = [
        "اهلا",
        "أهلا",
        "مرحبا",
        "سلام",
        "شلونك",
        "ازيك",
        "كيفك",
        "الو",
        "انت مين",
        "صباح",
        "مساء",
        "مين انت",
        "شكرا",
        "يعطيك العافية",
        "من انت",
        "تسلم",
        "الله يباركلك",
    ]
    if any(kw in normalized for kw in chit_chat_keywords):
        return "chit_chat"

    # 6. Quick Direct ('كلمتين ويسكت')
    quick_indicators = [
        "ينفع اخلط",
        "ينفع نخلط",
        "اخلط",
        "ارش الصبح ولا",
        "الصبح ولا بالليل",
        "الصبح ولا العصر",
        "فطر ولا بكتيريا",
        "حشرة ولا فطر",
        "مدة الامان كام",
        "فترة الامان كام",
        "يعني ايه phi",
        "اروي كل كام",
        "الري كل كام",
        "افضل وقت للرش",
        "ميعاد الرش",
    ]
    if any(qi in normalized for qi in quick_indicators):
        return "quick_direct"

    # 7. Comprehensive Protocol ('بروتوكول تفصيلي')
    comprehensive_indicators = [
        "برنامج تسميد",
        "جدول تسميد",
        "برنامج مكافحة",
        "جدول مكافحة",
        "مكافحة متكاملة",
        "من الزراعة للحصاد",
        "بالتفصيل",
        "فصلي",
        "خطوة بخطوة",
        "برنامج كامل",
        "دليل كامل",
    ]
    if any(ci in normalized for ci in comprehensive_indicators):
        return "comprehensive_protocol"

    # 8. Dosage / pesticide / fertilizer lookup indicators
    dosage_keywords = [
        "جرعة",
        "جرعات",
        "كمية",
        "نسبة",
        "معدل",
        "تسميد",
        "سماد",
        "مبيد",
        "تركيز",
        "معاملة",
        "npk",
        "urea",
        "يوريا",
        "لتر",
        "فدان",
        "رش",
    ]
    if any(kw in normalized for kw in dosage_keywords):
        return "dosage_lookup"

    # 9. Disease / pest identification indicators
    disease_keywords = [
        "مرض",
        "امراض",
        "اعراض",
        "اصابة",
        "عفن",
        "لفحة",
        "صدأ",
        "ذبول",
        "حشرة",
        "حشرات",
        "آفة",
        "آفات",
        "بكتيريا",
        "ديدان",
        "سوسة",
        "بياض",
    ]
    if any(kw in normalized for kw in disease_keywords):
        return "disease_query"

    # 10. Out-of-vocabulary / Random Arabic keymash without context
    agri_words = {
        "طماطم",
        "بطاطس",
        "قمح",
        "ذرة",
        "عنب",
        "مانجو",
        "مانجا",
        "زيتون",
        "ارز",
        "أرز",
        "بصل",
        "ثوم",
        "تفاح",
        "فراولة",
        "فلفل",
        "خيار",
        "كوسة",
        "باذنجان",
        "برتقال",
        "موالح",
        "نخيل",
        "نخل",
        "رمان",
        "موز",
        "تين",
        "كنتالوب",
        "بطيخ",
        "فول",
        "زرع",
        "محصول",
        "ارض",
        "غيط",
        "مزرعة",
        "شجر",
        "شجرة",
        "ورق",
        "ثمار",
        "عقد",
        "تزهير",
        "تقليم",
        "ري",
        "سقي",
        "طقس",
        "جو",
        "مطر",
        "حرارة",
    }
    question_words = {
        "ازاي",
        "كيف",
        "ليه",
        "امتى",
        "متى",
        "فين",
        "كام",
        "كم",
        "هل",
        "ماهو",
        "ما هو",
        "ما هي",
        "ايه",
        "ينفع",
        "ممكن",
        "طريقة",
    }
    has_agri = any(w in normalized for w in agri_words)
    has_q = any(w in normalized for w in question_words)
    words = normalized.split()
    if (
        not has_context
        and not has_agri
        and not has_q
        and len(words) <= 3
        and len(raw) <= 25
    ):
        return "unintelligible"

    return "general_advice"


def preprocess_query(
    query: str,
    lexicon: Dict[str, Any],
    vision_context: Optional[Dict[str, Any]] = None,
    has_context: bool = False,
) -> Dict[str, Any]:
    """Run full preprocessing pipeline on input query.

    Returns structured metadata including normalized query, canonical terms, intent,
    and vision context if provided.
    """
    raw_query = query or ""
    normalized = normalize_arabic_text(raw_query)
    canonical = canonicalize_terms(raw_query, lexicon)
    active_has_context = has_context or bool(vision_context)
    intent = detect_query_intent(canonical, has_context=active_has_context)

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
