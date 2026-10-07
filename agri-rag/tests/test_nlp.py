from agri_rag.nlp.arabic import normalize_arabic, tokenize
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
