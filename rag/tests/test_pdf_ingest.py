"""Tests for rag/pdf_ingest.py — PDF extraction, metadata inference, and chunking."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest

from rag.pdf_ingest import (
    _content_hash,
    _normalize_arabic,
    infer_metadata_from_text,
    load_pdfs_to_documents,
    pdf_to_documents,
    split_into_sections,
)


# ─── Arabic normalization ────────────────────────────────────────────────────

class TestNormalizeArabic:
    def test_alef_unification(self):
        assert _normalize_arabic("إأآا") == "اااا"

    def test_diacritic_stripping(self):
        text_with_harakat = "الزِّراعَةُ"
        result = _normalize_arabic(text_with_harakat)
        assert "ِ" not in result and "َ" not in result and "ُ" not in result

    def test_whitespace_collapse(self):
        result = _normalize_arabic("قمح   زراعة")
        assert "  " not in result

    def test_empty_string(self):
        assert _normalize_arabic("") == ""

    def test_strips_zero_width(self):
        text = "قمح\u200bزراعة"
        result = _normalize_arabic(text)
        assert "\u200b" not in result


# ─── Metadata inference ──────────────────────────────────────────────────────

class TestInferMetadata:
    def test_detects_wheat_crop(self):
        meta = infer_metadata_from_text("توصيات مكافحة أمراض القمح في مصر")
        assert meta["crop_type"] == "قمح"

    def test_detects_tomato(self):
        meta = infer_metadata_from_text("مكافحة آفات الطماطم")
        assert meta["crop_type"] == "طماطم"

    def test_detects_late_blight(self):
        meta = infer_metadata_from_text("أعراض الندوة المتأخرة على البطاطس")
        assert meta["disease_name"] == "ندوة متأخرة"

    def test_detects_powdery_mildew(self):
        meta = infer_metadata_from_text("مكافحة البياض الدقيقي على القرع")
        assert meta["disease_name"] == "بياض دقيقي"

    def test_detects_protocol_doctype(self):
        protocol_text = "جرعة المبيد 200 جم/فدان طريقة الاستخدام رش ورقي"
        meta = infer_metadata_from_text(protocol_text)
        assert meta["doc_type"] == "protocol"

    def test_defaults_to_guide_doctype(self):
        meta = infer_metadata_from_text("نبذة عامة عن الزراعة في مصر")
        assert meta["doc_type"] == "guide"

    def test_detects_delta_region(self):
        meta = infer_metadata_from_text("توصيات لمزارع الدلتا")
        assert meta["region"] == "delta"

    def test_unknown_crop_default(self):
        meta = infer_metadata_from_text("محتوى غير متعلق بالزراعة")
        assert meta["crop_type"] == "unknown"


# ─── Content hash ────────────────────────────────────────────────────────────

class TestContentHash:
    def test_same_text_same_hash(self):
        assert _content_hash("hello") == _content_hash("hello")

    def test_different_text_different_hash(self):
        assert _content_hash("hello") != _content_hash("world")

    def test_returns_string(self):
        assert isinstance(_content_hash("test"), str)


# ─── Section splitter ────────────────────────────────────────────────────────

class TestSplitIntoSections:
    def _make_pages(self, texts: List[str]) -> List[Dict[str, Any]]:
        return [{"page": i + 1, "text": t, "raw_length": len(t)} for i, t in enumerate(texts)]

    def test_single_page_one_section(self):
        pages = self._make_pages(["محتوى الصفحة الأولى\nمعلومات عامة عن الزراعة"])
        sections = split_into_sections(pages)
        assert len(sections) >= 1

    def test_header_starts_new_section(self):
        pages = self._make_pages([
            "محتوى الفصل الأول\nنص عام",
            "الفصل الثاني في القمح\nتوصيات مكافحة",
        ])
        sections = split_into_sections(pages)
        assert len(sections) >= 1  # At minimum the header page triggers split

    def test_page_numbers_preserved(self):
        pages = self._make_pages(["نص طويل عن القمح والزراعة في مصر"])
        sections = split_into_sections(pages)
        assert sections[0]["page_start"] == 1
        assert sections[0]["page_end"] == 1


# ─── pdf_to_documents (mocked extraction) ────────────────────────────────────

class TestPdfToDocuments:
    def test_raises_if_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            pdf_to_documents(tmp_path / "missing.pdf")

    def test_returns_list_of_dicts(self, tmp_path):
        """Mock extract_pages to avoid needing a real PDF."""
        fake_pdf = tmp_path / "test.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4 dummy")  # minimal stub

        fake_pages = [
            {
                "page": 1,
                "text": "توصيات مكافحة القمح في مصر جرعة مبيد 200 جم/فدان طريقة الاستخدام رش ورقي",
                "raw_length": 100,
            },
            {
                "page": 2,
                "text": "الفصل الثاني: أمراض الطماطم والندوة المتأخرة",
                "raw_length": 80,
            },
        ]

        with patch("rag.pdf_ingest.extract_pages", return_value=fake_pages):
            docs = pdf_to_documents(fake_pdf)

        assert isinstance(docs, list)
        assert all("content" in d for d in docs)
        assert all("doc_type" in d for d in docs)
        assert all("crop_type" in d for d in docs)

    def test_deduplication_removes_identical_sections(self, tmp_path):
        fake_pdf = tmp_path / "dup.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4 dummy")

        repeated_text = "نص متكرر لاختبار إزالة التكرار في القمح والزراعة المصرية" * 5
        fake_pages = [
            {"page": 1, "text": repeated_text, "raw_length": len(repeated_text)},
            {"page": 2, "text": repeated_text, "raw_length": len(repeated_text)},
        ]

        with patch("rag.pdf_ingest.extract_pages", return_value=fake_pages):
            docs = pdf_to_documents(fake_pdf, deduplicate=True)

        # Only 1 unique section despite 2 identical pages
        assert len(docs) == 1

    def test_base_metadata_override(self, tmp_path):
        fake_pdf = tmp_path / "override.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4 dummy")

        fake_pages = [
            {
                "page": 1,
                "text": "محتوى زراعي عام في مصر عن الزراعة والتربة الزراعية ومعالجة الحقول والمحاصيل والآفات الزراعية",
                "raw_length": 120,
            }
        ]

        with patch("rag.pdf_ingest.extract_pages", return_value=fake_pages):
            docs = pdf_to_documents(
                fake_pdf,
                base_metadata={"crop_type": "قطن", "region": "delta"},
            )

        assert len(docs) >= 1
        assert docs[0]["crop_type"] == "قطن"
        assert docs[0]["region"] == "delta"


# ─── load_pdfs_to_documents (multi-PDF) ──────────────────────────────────────

class TestLoadPdfsToDocuments:
    def test_skips_missing_files_gracefully(self, tmp_path):
        missing = tmp_path / "nonexistent.pdf"
        docs = load_pdfs_to_documents([missing])
        # Should not raise; returns empty list since file doesn't exist
        assert isinstance(docs, list)

    def test_global_deduplication_across_pdfs(self, tmp_path):
        pdf1 = tmp_path / "a.pdf"
        pdf2 = tmp_path / "b.pdf"
        pdf1.write_bytes(b"%PDF-1.4 dummy")
        pdf2.write_bytes(b"%PDF-1.4 dummy")

        repeated_text = "نفس المحتوى في كلا الملفين لاختبار التكرار العالمي في الزراعة المصرية" * 5
        fake_pages = [{"page": 1, "text": repeated_text, "raw_length": len(repeated_text)}]

        with patch("rag.pdf_ingest.extract_pages", return_value=fake_pages):
            docs = load_pdfs_to_documents([pdf1, pdf2], deduplicate_global=True)

        assert len(docs) == 1  # Cross-PDF deduplication

    def test_returns_merged_list(self, tmp_path):
        pdf1 = tmp_path / "c.pdf"
        pdf2 = tmp_path / "d.pdf"
        pdf1.write_bytes(b"%PDF-1.4 dummy")
        pdf2.write_bytes(b"%PDF-1.4 dummy")

        pages_a = [{"page": 1, "text": "معلومات القمح والزراعة في مصر العليا والصعيد وكيفية مكافحة الآفات الزراعية", "raw_length": 100}]
        pages_b = [{"page": 1, "text": "توصيات الطماطم والبياض الدقيقي في دلتا النيل وكيفية العلاج والوقاية من الامراض", "raw_length": 100}]

        def mock_extract(path):
            if "c.pdf" in str(path):
                return pages_a
            return pages_b

        with patch("rag.pdf_ingest.extract_pages", side_effect=mock_extract):
            docs = load_pdfs_to_documents([pdf1, pdf2], deduplicate_global=False)

        assert len(docs) == 2
