"""PDF ingestion pipeline for Egyptian agricultural knowledge-base PDFs.

Supports:
- Arabic layout-aware extraction via PyMuPDF (fitz) with fallback to pdfplumber
- Automatic metadata extraction (crop, disease, region) from section headers
- Page-level deduplication via content hashing
- Two-pass page structure analysis (headers → sections → paragraphs)
- Integration with existing chunk_agricultural_guide / chunk_treatment_protocol logic
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

logger = logging.getLogger(__name__)

# ─── Arabic section-header patterns for metadata extraction ──────────────────

CROP_KEYWORDS: Dict[str, List[str]] = {
    "قمح": ["قمح", "القمح", "حبوب"],
    "أرز": ["أرز", "الأرز", "رز"],
    "طماطم": ["طماطم", "الطماطم", "بندورة"],
    "قطن": ["قطن", "القطن"],
    "ذرة": ["ذرة", "الذرة", "كوز"],
    "بطاطس": ["بطاطس", "البطاطس", "بطاطا"],
    "بصل": ["بصل", "البصل"],
    "خيار": ["خيار", "الخيار"],
    "فول": ["فول", "الفول", "فاصوليا"],
    "سمسم": ["سمسم", "السمسم"],
    "بنجر": ["بنجر", "السكر", "شوندر"],
    "قصب": ["قصب", "السكر", "عصير"],
    "برسيم": ["برسيم", "البرسيم"],
    "عنب": ["عنب", "العنب", "كرمة"],
    "موز": ["موز", "الموز"],
    "مانجو": ["مانجو", "المانجو"],
    "حمضيات": ["برتقال", "ليمون", "منديرينا", "يوسفي", "جريب فروت"],
    "زيتون": ["زيتون", "الزيتون"],
    "فراولة": ["فراولة", "الفراولة"],
    "كوسة": ["كوسة", "الكوسة", "كوسا"],
    "باذنجان": ["باذنجان", "الباذنجان"],
    "فلفل": ["فلفل", "الفلفل"],
}

DISEASE_KEYWORDS: Dict[str, List[str]] = {
    "ندوة متأخرة": ["ندوة متأخرة", "الندوة المتأخرة", "اللفحة"],
    "بياض دقيقي": ["بياض دقيقي", "البياض الدقيقي", "أوديوم"],
    "صدأ أصفر": ["صدأ أصفر", "الصدأ الأصفر"],
    "صدأ بني": ["صدأ بني", "الصدأ البني"],
    "تفحم": ["تفحم", "التفحم"],
    "تبقع": ["تبقع", "التبقع", "بقع ورقية"],
    "عفن رمادي": ["عفن رمادي", "بوتريتس"],
    "ذبابة البيضاء": ["ذبابة بيضاء", "الذبابة البيضاء"],
    "حشرة المن": ["من", "حشرة المن", "أفيدات"],
    "التربس": ["تربس", "التربس"],
    "عنكبوت أحمر": ["عنكبوت أحمر", "أكاروس"],
    "دودة قارضة": ["دودة قارضة", "قوارض"],
    "ذبابة الفاكهة": ["ذبابة الفاكهة"],
    "حفار الساق": ["حفار الساق", "دودة الساق"],
}

PROTOCOL_MARKERS = [
    "جرعة", "جم/فدان", "سم/فدان", "لتر/فدان", "جزء في المليون",
    "طريقة الاستخدام", "توصية", "يرش", "يعامل", "مبيد", "تركيز",
]

REGION_KEYWORDS: Dict[str, List[str]] = {
    "delta": ["دلتا", "الدلتا", "مصر السفلى"],
    "upper_egypt": ["الصعيد", "مصر العليا", "أسيوط", "سوهاج", "أسوان"],
    "sinai": ["سيناء", "الشرقية"],
    "nile_valley": ["وادي النيل", "وادي"],
    "egypt_general": ["مصر", "جمهورية"],
}


# ─── Text Normalisation ───────────────────────────────────────────────────────

def _normalize_arabic(text: str) -> str:
    """Normalize Arabic Unicode forms, strip diacritics and extra whitespace."""
    # Normalize unicode
    text = unicodedata.normalize("NFKC", text)
    # Unify alef forms
    text = re.sub(r"[إأآ]", "ا", text)
    # ى → ي (except at end of word when it stays ى — keep simple here)
    # Strip tashkeel / harakat
    text = re.sub(r"[\u064B-\u065F\u0670]", "", text)
    # Collapse multiple spaces / zero-width chars
    text = re.sub(r"[\u200b-\u200f\u202a-\u202e]", "", text)
    text = re.sub(r" {2,}", " ", text)
    text = text.strip()
    return text


def _content_hash(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


# ─── Metadata Inference from Text ────────────────────────────────────────────

def infer_metadata_from_text(text: str, filename: str = "") -> Dict[str, Any]:
    """Scan text for crop, disease, region keywords and return best match."""
    text_lower = text.lower()
    fn_lower = filename.lower()

    crop_type = "unknown"
    disease_name = "unknown"
    region = "egypt_general"
    doc_type = "guide"

    # Detect crop
    for crop, aliases in CROP_KEYWORDS.items():
        if any(alias in text_lower for alias in aliases):
            crop_type = crop
            break

    # Detect disease
    for disease, aliases in DISEASE_KEYWORDS.items():
        if any(alias in text_lower for alias in aliases):
            disease_name = disease
            break

    # Detect region
    for reg, aliases in REGION_KEYWORDS.items():
        if any(alias in text_lower for alias in aliases):
            region = reg
            break

    # Detect protocol vs guide
    protocol_score = sum(1 for marker in PROTOCOL_MARKERS if marker in text_lower)
    if protocol_score >= 2:
        doc_type = "protocol"

    return {
        "crop_type": crop_type,
        "disease_name": disease_name,
        "region": region,
        "doc_type": doc_type,
        "source_doc": filename,
    }


# ─── PyMuPDF Extractor ────────────────────────────────────────────────────────

def _extract_pages_pymupdf(pdf_path: Path) -> Generator[Dict[str, Any], None, None]:
    """Extract text page-by-page using PyMuPDF with RTL/Arabic support."""
    try:
        import pymupdf as fitz  # Preferred import (>=1.24)
    except ImportError:
        import fitz  # Legacy fallback

    doc = fitz.open(str(pdf_path))
    logger.info(f"PyMuPDF: opened '{pdf_path.name}' — {len(doc)} pages")

    for page_num, page in enumerate(doc, start=1):
        # Use dict-based extraction for better Arabic ordering
        blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
        page_text_parts: List[str] = []

        for block in blocks:
            if block.get("type") != 0:  # Skip image blocks
                continue
            for line in block.get("lines", []):
                line_text = " ".join(
                    span["text"] for span in line.get("spans", [])
                    if span["text"].strip()
                )
                if line_text.strip():
                    page_text_parts.append(line_text.strip())

        raw_text = "\n".join(page_text_parts)
        normalized = _normalize_arabic(raw_text)

        if len(normalized) < 30:  # Skip nearly-empty / image-only pages
            continue

        yield {
            "page": page_num,
            "text": normalized,
            "raw_length": len(raw_text),
        }

    doc.close()


# ─── pdfplumber Fallback ──────────────────────────────────────────────────────

def _extract_pages_pdfplumber(pdf_path: Path) -> Generator[Dict[str, Any], None, None]:
    """Extract text page-by-page using pdfplumber as fallback."""
    import pdfplumber

    with pdfplumber.open(str(pdf_path)) as pdf:
        logger.info(f"pdfplumber: opened '{pdf_path.name}' — {len(pdf.pages)} pages")
        for page_num, page in enumerate(pdf.pages, start=1):
            raw_text = page.extract_text(x_tolerance=3, y_tolerance=3) or ""
            normalized = _normalize_arabic(raw_text)
            if len(normalized) < 30:
                continue
            yield {
                "page": page_num,
                "text": normalized,
                "raw_length": len(raw_text),
            }


# ─── Page-level extractor dispatcher ─────────────────────────────────────────

def extract_pages(pdf_path: Path) -> List[Dict[str, Any]]:
    """Extract all pages, preferring PyMuPDF with pdfplumber fallback."""
    try:
        pages = list(_extract_pages_pymupdf(pdf_path))
        if pages:
            return pages
        logger.warning("PyMuPDF returned no content, falling back to pdfplumber")
    except ImportError:
        logger.warning("PyMuPDF not available, using pdfplumber")
    except Exception as exc:
        logger.warning(f"PyMuPDF failed ({exc}), using pdfplumber")

    return list(_extract_pages_pdfplumber(pdf_path))


# ─── Section splitter ─────────────────────────────────────────────────────────

def split_into_sections(pages: List[Dict[str, Any]], pages_per_section: int = 5) -> List[Dict[str, Any]]:
    """Group consecutive pages into sections based on detected header changes.

    A new section starts when a page begins with a recognized Arabic heading.
    For PDFs with no structured headers, pages are grouped in fixed-size windows
    of `pages_per_section` pages to create manageable retrieval chunks.
    """
    HEADER_PATTERN = re.compile(
        r"^(?:الفصل|الباب|القسم|محصول|مكافحة|توصيات|إرشادات|برنامج)\s+.{1,60}$",
        re.MULTILINE,
    )

    sections: List[Dict[str, Any]] = []
    current_section_pages: List[Dict[str, Any]] = []
    current_header = "مقدمة"
    found_any_header = False

    for page in pages:
        headers_found = HEADER_PATTERN.findall(page["text"])
        if headers_found and current_section_pages:
            found_any_header = True
            sections.append({
                "header": current_header,
                "text": "\n\n".join(p["text"] for p in current_section_pages),
                "page_start": current_section_pages[0]["page"],
                "page_end": current_section_pages[-1]["page"],
            })
            current_section_pages = []
            current_header = headers_found[0].strip()

        current_section_pages.append(page)

    # Flush remaining pages
    if current_section_pages:
        sections.append({
            "header": current_header,
            "text": "\n\n".join(p["text"] for p in current_section_pages),
            "page_start": current_section_pages[0]["page"],
            "page_end": current_section_pages[-1]["page"],
        })

    # If no structured headers were found, fall back to fixed page-window grouping
    if not found_any_header and len(sections) == 1 and len(pages) > pages_per_section:
        logger.info("No structured headers detected; using page-window grouping.")
        sections = []
        for i in range(0, len(pages), pages_per_section):
            window = pages[i : i + pages_per_section]
            sections.append({
                "header": f"صفحات {window[0]['page']}–{window[-1]['page']}",
                "text": "\n\n".join(p["text"] for p in window),
                "page_start": window[0]["page"],
                "page_end": window[-1]["page"],
            })

    return sections


# ─── Main PDF → Document converter ───────────────────────────────────────────

def pdf_to_documents(
    pdf_path: str | Path,
    base_metadata: Optional[Dict[str, Any]] = None,
    deduplicate: bool = True,
) -> List[Dict[str, Any]]:
    """Parse a PDF and return a list of section-level documents ready for ingest.

    Args:
        pdf_path: Path to the PDF file.
        base_metadata: Optional overrides (crop_type, region, etc.).
        deduplicate: Skip sections with duplicate content hashes.

    Returns:
        List of dicts with keys: content, source_doc, doc_type, crop_type,
        disease_name, region, page_start, page_end, section_header.
    """
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")

    logger.info(f"Starting PDF extraction: {path.name}")
    pages = extract_pages(path)
    logger.info(f"Extracted {len(pages)} usable pages from '{path.name}'")

    sections = split_into_sections(pages)
    logger.info(f"Identified {len(sections)} sections in '{path.name}'")

    seen_hashes: set[str] = set()
    documents: List[Dict[str, Any]] = []
    MAX_SECTION_CHARS = 20_000  # Split sections exceeding this into sub-chunks

    for section in sections:
        text = section["text"].strip()
        if not text or len(text) < 40:
            continue

        # Split oversized sections into ~MAX_SECTION_CHARS chunks
        text_chunks: List[str]
        if len(text) > MAX_SECTION_CHARS:
            # Split on paragraph boundary (double newline) to keep coherence
            paragraphs = text.split("\n\n")
            current, text_chunks = "", []
            for para in paragraphs:
                if len(current) + len(para) <= MAX_SECTION_CHARS:
                    current += ("\n\n" if current else "") + para
                else:
                    if current:
                        text_chunks.append(current)
                    current = para
            if current:
                text_chunks.append(current)
        else:
            text_chunks = [text]

        for chunk_text in text_chunks:
            content_hash = _content_hash(chunk_text)
            if deduplicate and content_hash in seen_hashes:
                logger.debug(f"Skipping duplicate section (hash={content_hash[:8]})")
                continue
            seen_hashes.add(content_hash)

            # Infer metadata from this sub-chunk
            meta = infer_metadata_from_text(chunk_text, filename=path.name)
            if base_metadata:
                meta.update({k: v for k, v in base_metadata.items() if v is not None})

            documents.append({
                "content": chunk_text,
                "source_doc": path.name,
                "doc_type": meta["doc_type"],
                "crop_type": meta["crop_type"],
                "disease_name": meta["disease_name"],
                "region": meta["region"],
                "page_start": section["page_start"],
                "page_end": section["page_end"],
                "section_header": section["header"],
            })

    logger.info(f"Produced {len(documents)} unique documents from '{path.name}'")
    return documents


# ─── Multi-PDF batch loader ───────────────────────────────────────────────────

def load_pdfs_to_documents(
    pdf_paths: List[str | Path],
    base_metadata: Optional[Dict[str, Any]] = None,
    deduplicate_global: bool = True,
) -> List[Dict[str, Any]]:
    """Load multiple PDFs and merge into a single document list.

    Args:
        pdf_paths: List of PDF file paths to process.
        base_metadata: Optional metadata overrides applied to all PDFs.
        deduplicate_global: Remove cross-file duplicate sections.

    Returns:
        Merged list of section documents.
    """
    all_documents: List[Dict[str, Any]] = []
    global_hashes: set[str] = set()

    for pdf_path in pdf_paths:
        try:
            docs = pdf_to_documents(pdf_path, base_metadata=base_metadata)
            if deduplicate_global:
                unique_docs = []
                for doc in docs:
                    h = _content_hash(doc["content"])
                    if h not in global_hashes:
                        global_hashes.add(h)
                        unique_docs.append(doc)
                docs = unique_docs
            all_documents.extend(docs)
            logger.info(f"Total so far: {len(all_documents)} documents")
        except Exception as exc:
            logger.error(f"Failed to process '{pdf_path}': {exc}", exc_info=True)

    return all_documents


# ─── CLI / Script entry point ─────────────────────────────────────────────────

def main(pdf_paths: List[str], output_jsonl: str = "data/extracted_documents.jsonl") -> None:
    """Extract PDFs and write documents to a JSONL file for inspection / re-ingestion."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")
    paths = [Path(p) for p in pdf_paths]
    documents = load_pdfs_to_documents(paths)

    out_path = Path(output_jsonl)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(out_path, "w", encoding="utf-8") as f:
        for doc in documents:
            f.write(json.dumps(doc, ensure_ascii=False) + "\n")

    print(f"\n✅ Extracted {len(documents)} documents → {out_path}")
    # Show sample
    if documents:
        sample = documents[0]
        print(f"\n--- Sample document ---")
        print(f"Source : {sample['source_doc']}")
        print(f"Pages  : {sample.get('page_start')}–{sample.get('page_end')}")
        print(f"Type   : {sample['doc_type']}")
        print(f"Crop   : {sample['crop_type']}")
        print(f"Disease: {sample['disease_name']}")
        print(f"Region : {sample['region']}")
        print(f"Text   : {sample['content'][:300]}...")


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m rag.pdf_ingest <pdf1> [pdf2] ...")
        sys.exit(1)
    main(sys.argv[1:])
