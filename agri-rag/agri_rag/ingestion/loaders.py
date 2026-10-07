"""Document loaders: Markdown / text (with optional YAML front matter) and PDF."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

log = logging.getLogger(__name__)

_FRONT_MATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
SUPPORTED = {".md", ".txt", ".pdf"}


@dataclass
class Document:
    source: str  # file name, used for citations and stale-chunk cleanup
    title: str
    text: str
    metadata: dict = field(default_factory=dict)  # crop, doc_type, org, year, ...


def _parse_front_matter(raw: str) -> tuple[dict, str]:
    match = _FRONT_MATTER.match(raw)
    if not match:
        return {}, raw
    return (yaml.safe_load(match.group(1)) or {}), raw[match.end():]


def _first_heading(text: str) -> str | None:
    for line in text.splitlines():
        if line.startswith("#"):
            return line.lstrip("# ").strip()
    return None


def _load_text(path: Path) -> Document:
    meta, body = _parse_front_matter(path.read_text(encoding="utf-8"))
    title = meta.pop("title", None) or _first_heading(body) or path.stem
    return Document(path.name, title, body, meta)


def _load_pdf(path: Path) -> Document:
    from pypdf import PdfReader  # lazy: optional dependency path

    reader = PdfReader(str(path))
    pages = [(p.extract_text() or "").strip() for p in reader.pages]
    text = "\n\n".join(p for p in pages if p)
    if not text:
        log.warning("%s has no extractable text (scanned?). Run it through the OCR engine first.", path.name)
    else:
        log.warning(
            "%s: Arabic PDF text extraction can reverse/disconnect letters. "
            "Prefer .md/.txt/.docx-exported sources for the knowledge base and spot-check the chunks.",
            path.name,
        )
    return Document(path.name, path.stem.replace("_", " "), text, {"doc_type": "pdf"})


def load_documents(directory: Path) -> list[Document]:
    docs: list[Document] = []
    for path in sorted(Path(directory).rglob("*")):
        if path.suffix.lower() not in SUPPORTED or not path.is_file():
            continue
        doc = _load_pdf(path) if path.suffix.lower() == ".pdf" else _load_text(path)
        if doc.text.strip():
            docs.append(doc)
        else:
            log.warning("Skipping empty document %s", path.name)
    return docs
