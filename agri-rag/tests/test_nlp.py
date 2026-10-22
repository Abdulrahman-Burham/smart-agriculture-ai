from agri_rag.nlp.arabic import classify_user_query, normalize_arabic, tokenize
from agri_rag.nlp.glossary import Glossary
from agri_rag.config import Settings


def test_normalize_unifies_letters_and_digits():
    assert normalize_arabic("الأَرْضُ مالحةٌ ٨٫٢") == "الارض مالحه 8.2"
    assert normalize_arabic("إنتاجية") == normalize_arabic("انتاجيه")


def test_tokenize_drops_stopwords_and_prefix():
    assert "ارض" in tokenize("الأرض عندي في الحقل")
    assert "في" not in tokenize("الأرض في الحقل")


def test_glossary_expands_dialect_to_canonical():
    g = Glossary.load(Settings().glossary_path)
    exp = g.expand("الورق بتاع القوطة بيصفر")
    canon = {c for _, c in exp.matches}
    assert "طماطم" in canon and "اصفرار الأوراق" in canon
    assert "طماطم" in exp.expanded


def test_glossary_crop_canonicalisation():
    g = Glossary.load(Settings().glossary_path)
    assert g.canonicalize("قوطة", "crop") == "طماطم"
    assert g.canonicalize("محصول مجهول", "crop") == "محصول مجهول"


def test_classify_user_query_intents():
    # 1. Unintelligible inputs (gibberish, symbols, random characters)
    q_gib = classify_user_query("حهىل")
    assert q_gib.intent == "unintelligible"
    assert q_gib.is_gibberish is True
    assert not q_gib.requires_retrieval
    assert q_gib.suggested_fast_response is not None

    q_sym = classify_user_query("????!#$$")
    assert q_sym.intent == "unintelligible"

    q_lat = classify_user_query("asdfghjkl")
    assert q_lat.intent == "unintelligible"

    # 2. Ambiguous clarification needed when no prior context exists
    q_vague = classify_user_query("اعمل ايه؟", has_context=False)
    assert q_vague.intent == "needs_clarification"
    assert not q_vague.requires_retrieval
    assert "تحت أمرك" in (q_vague.suggested_fast_response or "")

    # Follow-up "اعمل ايه؟" with prior crop/history context should proceed to standard response
    q_follow = classify_user_query("اعمل ايه؟", has_context=True)
    assert q_follow.intent == "standard_agricultural"
    assert q_follow.requires_retrieval is True

    # 3. Chit-chat & Greetings
    q_hi = classify_user_query("صباح الخير يا هندسة")
    assert q_hi.intent == "chit_chat"
    assert not q_hi.requires_retrieval

    # 4. Quick direct ("كلمتين ويسكت")
    q_quick = classify_user_query("ينفع اخلط نحاس مع سماد ورقي؟")
    assert q_quick.intent == "quick_direct"
    assert q_quick.requires_retrieval is True
    assert q_quick.suggested_max_tokens <= 250
    assert "كلمتين وبس" in q_quick.dynamic_instruction

    # 5. Comprehensive protocol ("برنامج كامل وتفصيلي")
    q_comp = classify_user_query("عايز برنامج تسميد كامل للبطاطس من الزراعة للحصاد")
    assert q_comp.intent == "comprehensive_protocol"
    assert q_comp.requires_retrieval is True
    assert q_comp.suggested_max_tokens >= 1000
    assert "بروتوكول زراعي متكامل" in q_comp.dynamic_instruction
