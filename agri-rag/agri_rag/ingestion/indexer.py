"""Index a knowledge directory into the vector store (idempotent)."""
from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from ..config import Settings
from ..retrieval.vectorstore import ChromaStore
from .chunking import chunk_document
from .loaders import load_documents


@dataclass
class IndexReport:
    documents: int
    chunks: int
    seconds: float
    sources: list[str]


def index_directory(directory: Path, store: ChromaStore, settings: Settings, reset: bool = False) -> IndexReport:
    start = time.perf_counter()
    if reset:
        store.reset()
    docs = load_documents(directory)
    total = 0
    for doc in docs:
        chunks = chunk_document(doc, settings.chunk_max_chars, settings.chunk_overlap_chars)
        store.delete_source(doc.source)  # remove stale chunks of an edited file
        store.upsert(chunks)
        total += len(chunks)
    return IndexReport(len(docs), total, round(time.perf_counter() - start, 2), [d.source for d in docs])
