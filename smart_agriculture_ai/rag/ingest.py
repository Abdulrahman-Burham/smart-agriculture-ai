"""Knowledge-base ingestion for agricultural guides and treatment protocols."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any


def load_documents(paths: list[str]) -> list[dict[str, Any]]:
    """Load text documents from a list of file paths."""

    documents: list[dict[str, Any]] = []
    for path in paths:
        file_path = Path(path)
        if not file_path.exists():
            continue

        text = file_path.read_text(encoding="utf-8")
        documents.append(
            {
                "id": str(uuid.uuid4()),
                "source_doc": file_path.name,
                "text": text,
                "doc_type": "guide" if "guide" in file_path.name.lower() else "protocol",
                "crop_type": "unknown",
                "disease_name": "unknown",
                "region": "unknown",
            }
        )
    return documents


def chunk_documents(documents: list[dict[str, Any]], chunk_size: int = 500, overlap: int = 75) -> list[dict[str, Any]]:
    """Split documents into semantic chunk blocks while preserving protocols as single units."""

    chunks: list[dict[str, Any]] = []
    for document in documents:
        text = document.get("text", "")
        if not text:
            continue

        paragraphs = [section.strip() for section in text.split("\n\n") if section.strip()]
        current = ""
        for paragraph in paragraphs:
            if document.get("doc_type") == "protocol" and len(paragraph) > chunk_size:
                chunks.append(
                    {
                        "id": str(uuid.uuid4()),
                        "content": paragraph,
                        "metadata": {
                            "crop_type": document.get("crop_type", "unknown"),
                            "disease_name": document.get("disease_name", "unknown"),
                            "region": document.get("region", "unknown"),
                            "source_doc": document.get("source_doc", "unknown"),
                            "doc_type": "protocol",
                        },
                    }
                )
                continue

            if len(current) + len(paragraph) <= chunk_size:
                current = current + ("\n\n" if current else "") + paragraph
            else:
                if current:
                    chunks.append(
                        {
                            "id": str(uuid.uuid4()),
                            "content": current,
                            "metadata": {
                                "crop_type": document.get("crop_type", "unknown"),
                                "disease_name": document.get("disease_name", "unknown"),
                                "region": document.get("region", "unknown"),
                                "source_doc": document.get("source_doc", "unknown"),
                                "doc_type": document.get("doc_type", "guide"),
                            },
                        }
                    )
                current = paragraph

        if current:
            chunks.append(
                {
                    "id": str(uuid.uuid4()),
                    "content": current,
                    "metadata": {
                        "crop_type": document.get("crop_type", "unknown"),
                        "disease_name": document.get("disease_name", "unknown"),
                        "region": document.get("region", "unknown"),
                        "source_doc": document.get("source_doc", "unknown"),
                        "doc_type": document.get("doc_type", "guide"),
                    },
                }
            )

    return chunks


def embed_and_store(chunks: list[dict[str, Any]], embedding_model: str, vector_store) -> list[str]:
    """Embed chunk content and upsert it into the configured vector store."""

    ids: list[str] = []
    documents = []
    for chunk in chunks:
        chunk_id = chunk.get("id", str(uuid.uuid4()))
        ids.append(chunk_id)
        documents.append({
            "id": chunk_id,
            "content": chunk.get("content", ""),
            "metadata": chunk.get("metadata", {}),
        })

    if vector_store is not None:
        vector_store.add_documents(documents)
    return ids


def build_bm25_index(chunks: list[dict[str, Any]]) -> object:
    """Create a BM25 index over the same chunk corpus used for vector storage."""

    from services.bm25_service import BM25Service

    corpus = [chunk.get("content", "") for chunk in chunks]
    return BM25Service().build_index(corpus)


def ingest_knowledge_base(paths: list[str], vector_store, embedding_model: str) -> dict[str, Any]:
    """Ingest all available text knowledge into the vector store and BM25 index."""

    documents = load_documents(paths)
    chunks = chunk_documents(documents)
    ids = embed_and_store(chunks, embedding_model, vector_store)
    bm25_index = build_bm25_index(chunks)

    return {
        "documents_loaded": len(documents),
        "chunks_created": len(chunks),
        "chunk_ids": ids,
        "bm25_index": bm25_index,
    }
