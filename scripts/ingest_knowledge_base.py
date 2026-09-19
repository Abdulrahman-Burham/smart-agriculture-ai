"""CLI script to ingest text guides or agricultural PDF knowledge bases."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from rag.pdf_ingest import load_pdfs_to_documents
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


def ingest_pdfs(
    pdf_paths: List[str | Path],
    output_jsonl: str | Path | None = None,
) -> Dict[str, Any]:
    """Extract and ingest PDF sections, optionally exporting parsed documents."""
    pipeline = RAGPipeline()
    documents = load_pdfs_to_documents(pdf_paths)

    if output_jsonl is not None:
        output_path = Path(output_jsonl)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as output:
            for document in documents:
                output.write(json.dumps(document, ensure_ascii=False) + "\n")

    if not documents:
        print("⚠️ No readable content found in the supplied PDF files.")
        return {"num_pdfs": len(pdf_paths), "num_documents": 0, "num_chunks": 0}

    result = pipeline.ingest_documents(documents)
    summary = {
        "num_pdfs": len(pdf_paths),
        "num_documents": result["num_documents"],
        "num_chunks": result["num_chunks"],
    }
    print(
        f"✅ Successfully ingested {summary['num_documents']} PDF sections "
        f"into {summary['num_chunks']} chunks!"
    )
    if output_jsonl is not None:
        print(f"📝 Parsed documents written to {output_jsonl}")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest Knowledge Base Directory")
    parser.add_argument(
        "--dir",
        default="data/sample_knowledge_base",
        help="Target text knowledge-base folder (default: data/sample_knowledge_base)",
    )
    parser.add_argument(
        "--pdf",
        nargs="+",
        help="One or more PDF files to extract and ingest instead of --dir",
    )
    parser.add_argument(
        "--output-jsonl",
        help="Optional JSONL path for extracted PDF section documents",
    )
    args = parser.parse_args()

    if args.pdf:
        ingest_pdfs(args.pdf, output_jsonl=args.output_jsonl)
    else:
        ingest_directory(args.dir)
