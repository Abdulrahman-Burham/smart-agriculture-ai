"""Ingestion and chunking module for agricultural guides and treatment protocols."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from rank_bm25 import BM25Okapi
except ImportError:
    class BM25Okapi:  # type: ignore[no-redef]
        """Lightweight fallback BM25 scorer when rank_bm25 is not installed."""
        def __init__(self, corpus: List[List[str]]):
            self.corpus = corpus

        def get_scores(self, query_tokens: List[str]) -> List[float]:
            q_set = set(query_tokens)
            return [float(len(q_set.intersection(doc))) for doc in self.corpus]

logger = logging.getLogger(__name__)


def chunk_agricultural_guide(
    doc: Dict[str, Any],
    chunk_size: int = 400,
    overlap: int = 60,
) -> List[Dict[str, Any]]:
    """Chunk agricultural guides by section/semantic boundary (300-500 tokens, ~15% overlap)."""
    text = doc.get("content") or doc.get("text") or ""
    if not text.strip():
        return []

    # Split by section / double newline boundaries
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks: List[Dict[str, Any]] = []
    current_chunk = ""
    # Base metadata that should propagate to chunks
    base_metadata = {
        "crop_type": doc.get("crop_type", "unknown"),
        "disease_name": doc.get("disease_name", "unknown"),
        "region": doc.get("region", "egypt_general"),
        "source_doc": doc.get("source_doc", "guide.txt"),
        "doc_type": doc.get("doc_type", "guide"),
    }
    if "page_start" in doc:
        base_metadata["page_start"] = doc["page_start"]
    if "page_end" in doc:
        base_metadata["page_end"] = doc["page_end"]
    if "section_header" in doc:
        base_metadata["section_header"] = doc["section_header"]

    for paragraph in paragraphs:
        # If single paragraph exceeds chunk limit, split by sentences
        if len(paragraph.split()) > chunk_size:
            sentences = [s.strip() for s in paragraph.replace("؛", ".").split(".") if s.strip()]
            for sentence in sentences:
                if len(current_chunk.split()) + len(sentence.split()) <= chunk_size:
                    current_chunk += (" " if current_chunk else "") + sentence + "."
                else:
                    if current_chunk:
                        chunks.append({
                            "chunk_id": str(uuid.uuid4()),
                            "content": current_chunk.strip(),
                            "metadata": base_metadata.copy(),
                        })
                    # Add overlap from tail of current_chunk
                    overlap_words = current_chunk.split()[-overlap:] if current_chunk else []
                    current_chunk = " ".join(overlap_words + [sentence + "."])
        else:
            if len(current_chunk.split()) + len(paragraph.split()) <= chunk_size:
                current_chunk += ("\n\n" if current_chunk else "") + paragraph
            else:
                if current_chunk:
                    chunks.append({
                        "chunk_id": str(uuid.uuid4()),
                        "content": current_chunk.strip(),
                        "metadata": base_metadata.copy(),
                    })
                overlap_words = current_chunk.split()[-overlap:] if current_chunk else []
                current_chunk = (" ".join(overlap_words) + "\n\n" if overlap_words else "") + paragraph

    if current_chunk.strip():
        chunks.append({
            "chunk_id": str(uuid.uuid4()),
            "content": current_chunk.strip(),
            "metadata": base_metadata.copy(),
        })

    return chunks


def chunk_treatment_protocol(doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Chunk treatment protocols as a SINGLE unit per disease/treatment block.

    Treatments must NEVER be split mid-instruction to prevent unsafe partial advice.
    """
    text = doc.get("content") or doc.get("text") or ""
    if not text.strip():
        return []

    # Split into discrete treatment blocks if multiple exist (separated by protocol dividers)
    blocks = [b.strip() for b in text.split("===") if b.strip()]
    if not blocks:
        blocks = [text.strip()]

    chunks: List[Dict[str, Any]] = []
    base_metadata = {
        "crop_type": doc.get("crop_type", "unknown"),
        "disease_name": doc.get("disease_name", "unknown"),
        "region": doc.get("region", "egypt_general"),
        "source_doc": doc.get("source_doc", "protocol.txt"),
        "doc_type": doc.get("doc_type", "protocol"),
    }
    if "page_start" in doc:
        base_metadata["page_start"] = doc["page_start"]
    if "page_end" in doc:
        base_metadata["page_end"] = doc["page_end"]
    if "section_header" in doc:
        base_metadata["section_header"] = doc["section_header"]

    for block in blocks:
        chunks.append({
            "chunk_id": str(uuid.uuid4()),
            "content": block,
            "metadata": base_metadata.copy(),
        })

    return chunks


def process_document(doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Determine document type and apply appropriate chunking logic."""
    doc_type = doc.get("doc_type", "guide")
    if doc_type == "protocol":
        return chunk_treatment_protocol(doc)
    return chunk_agricultural_guide(doc)


def build_bm25_corpus_index(chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Create a BM25Okapi sparse retrieval index over the document chunks."""
    corpus = [chunk["content"] for chunk in chunks]
    tokenized_corpus = [doc.lower().split() for doc in corpus]
    bm25 = BM25Okapi(tokenized_corpus)

    return {
        "bm25_index": bm25,
        "corpus_chunks": chunks,
    }


def ingest_text_documents(
    documents: List[Dict[str, Any]],
    vector_store: Any,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Process, chunk, embed into VectorStore, and build BM25 sparse index."""
    all_chunks: List[Dict[str, Any]] = []

    for doc in documents:
        doc_chunks = process_document(doc)
        all_chunks.extend(doc_chunks)

    # Upsert to VectorStore if provided
    if vector_store is not None and hasattr(vector_store, "add_documents"):
        vector_store.add_documents(all_chunks)

    # Build BM25 sparse index
    bm25_data = build_bm25_corpus_index(all_chunks)

    return {
        "num_documents": len(documents),
        "num_chunks": len(all_chunks),
        "chunks": all_chunks,
        "bm25_data": bm25_data,
    }
