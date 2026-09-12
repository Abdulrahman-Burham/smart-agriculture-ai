"""Tests for the ingestion module."""

from pathlib import Path

from rag.ingest import chunk_documents, load_documents


def test_load_documents(tmp_path):
    file_path = tmp_path / "guide.txt"
    file_path.write_text("Guide content for irrigation.\n\nMore detail here.", encoding="utf-8")
    docs = load_documents([str(file_path)])
    assert len(docs) == 1
    assert docs[0]["source_doc"] == file_path.name


def test_chunk_documents():
    docs = [{
        "text": "Section one.\n\nSection two.\n\nSection three.",
        "doc_type": "guide",
        "crop_type": "tomato",
        "disease_name": "blight",
        "region": "delta",
        "source_doc": "guide.txt",
    }]
    chunks = chunk_documents(docs, chunk_size=50, overlap=10)
    assert len(chunks) >= 1
    assert chunks[0]["metadata"]["doc_type"] in {"guide", "protocol"}
