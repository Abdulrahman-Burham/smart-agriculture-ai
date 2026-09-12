"""CLI Script to batch ingest text guides and protocols into Chroma Vector Store and BM25 Index."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, List

from rag.ingest import process_document
from rag.respond import RAGPipeline


def ingest_directory(data_dir: str | Path = "data/sample_knowledge_base") -> Dict[str, Any]:
    """Scan data directory for .txt files and ingest them into RAG pipeline."""
    dir_path = Path(data_dir)
    if not dir_path.exists():
        print(f"❌ Directory {dir_path} does not exist.")
        return {"num_documents": 0, "num_chunks": 0}

    pipeline = RAGPipeline()
    documents: List[Dict[str, Any]] = []

    for file_path in dir_path.glob("*.txt"):
        text = file_path.read_text(encoding="utf-8")
        filename_lower = file_path.name.lower()
        
        # Determine doc_type and metadata
        doc_type = "protocol" if "protocol" in filename_lower else "guide"
        crop_type = "potato" if "potato" in filename_lower else ("tomato" if "tomato" in filename_lower else "general")
        
        documents.append({
            "source_doc": file_path.name,
            "doc_type": doc_type,
            "crop_type": crop_type,
            "disease_name": "general",
            "region": "egypt_general",
            "content": text,
        })

    if not documents:
        print(f"⚠️ No .txt files found in {dir_path}")
        return {"num_documents": 0, "num_chunks": 0}

    print(f"📂 Found {len(documents)} text files in {dir_path}. Ingesting...")
    res = pipeline.ingest_documents(documents)
    print(f"✅ Successfully ingested {res['num_documents']} documents into {res['num_chunks']} chunks!")
    return res


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest Knowledge Base Directory")
    parser.add_argument("--dir", default="data/sample_knowledge_base", help="Target knowledge base folder")
    args = parser.parse_args()

    ingest_directory(args.dir)
