"""Heading-aware chunking.

Strategy (defined in Week 2 of the roadmap):
  1. Split by Markdown headings so a chunk never mixes two topics.
  2. Pack paragraphs (then sentences) up to `max_chars`, with a small overlap between
     consecutive chunks so facts that straddle a boundary remain retrievable.
  3. Prefix every chunk with "title > heading path": this contextual header materially
     improves both BM25 and dense retrieval for short, terse agricultural guidance.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from .loaders import Document

_HEADING = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!؟?؛])\s+")


@dataclass(frozen=True)
class Chunk:
    id: str
    text: str  # includes the contextual header
    body: str  # raw body without header (used for display/snippets)
    metadata: dict


def _sections(text: str) -> list[tuple[list[str], str]]:
    path: list[tuple[int, str]] = []
    sections: list[tuple[list[str], list[str]]] = [([], [])]
    for line in text.splitlines():
        m = _HEADING.match(line)
        if m:
            level = len(m.group(1))
            path = [(lvl, h) for lvl, h in path if lvl < level] + [(level, m.group(2))]
            sections.append(([h for _, h in path], []))
        else:
            sections[-1][1].append(line)
    return [(p, "\n".join(body).strip()) for p, body in sections if "\n".join(body).strip()]


def _units(body: str, max_chars: int) -> list[str]:
    units: list[str] = []
    for para in re.split(r"\n\s*\n", body):
        para = para.strip()
        if not para:
            continue
        if len(para) <= max_chars:
            units.append(para)
            continue
        for sentence in _SENTENCE_SPLIT.split(para):
            while len(sentence) > max_chars:  # pathological sentence: hard split on whitespace
                cut = sentence.rfind(" ", 0, max_chars) or max_chars
                units.append(sentence[:cut].strip())
                sentence = sentence[cut:].strip()
            if sentence:
                units.append(sentence)
    return units


def _pack(units: list[str], max_chars: int, overlap_chars: int) -> list[str]:
    chunks: list[list[str]] = []
    current: list[str] = []
    size = 0
    for unit in units:
        if current and size + len(unit) + 1 > max_chars:
            chunks.append(current)
            tail: list[str] = []
            tail_size = 0
            for prev in reversed(current):  # carry a short tail into the next chunk
                if tail_size + len(prev) > overlap_chars:
                    break
                tail.insert(0, prev)
                tail_size += len(prev)
            current, size = tail, tail_size
        current.append(unit)
        size += len(unit) + 1
    if current:
        chunks.append(current)
    return ["\n".join(c) for c in chunks]


def chunk_document(doc: Document, max_chars: int = 900, overlap_chars: int = 120) -> list[Chunk]:
    out: list[Chunk] = []
    for heading_path, body in _sections(doc.text):
        header = " › ".join([doc.title, *heading_path[1:]] if heading_path and heading_path[0] == doc.title
                            else [doc.title, *heading_path])
        for piece in _pack(_units(body, max_chars), max_chars, overlap_chars):
            idx = len(out)
            digest = hashlib.sha1(f"{doc.source}|{idx}|{piece}".encode()).hexdigest()[:16]
            meta = {
                "source": doc.source,
                "title": doc.title,
                "section": " › ".join(heading_path),
                "chunk_index": idx,
                "crop": str(doc.metadata.get("crop", "عام")),
                "doc_type": str(doc.metadata.get("doc_type", "guide")),
                "org": str(doc.metadata.get("org", "")),
                "year": str(doc.metadata.get("year", "")),
            }
            out.append(Chunk(digest, f"{header}\n{piece}", piece, meta))
    return out
