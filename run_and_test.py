"""Live server launcher and integration validator."""

from __future__ import annotations

import time
import requests
import threading
import uvicorn
from app.main import app


def start_server():
    uvicorn.run(app, host="127.0.0.1", port=8080, log_level="error")


if __name__ == "__main__":
    print("🚀 Starting FastAPI Integration Gateway on http://127.0.0.1:8080...")
    thread = threading.Thread(target=start_server, daemon=True)
    thread.start()
    time.sleep(1.5)

    print("\n1. Testing GET /health...")
    h_res = requests.get("http://127.0.0.1:8080/health").json()
    print(f"   Response: {h_res}")

    print("\n2. Ingesting sample knowledge base documents into live FastAPI pipeline...")
    from pathlib import Path
    docs = []
    for p in Path("data/sample_knowledge_base").glob("*.txt"):
        docs.append({"source_doc": p.name, "doc_type": "protocol" if "protocol" in p.name else "guide", "crop_type": "potato", "content": p.read_text(encoding="utf-8")})
    from app.main import rag_pipeline
    rag_pipeline.ingest_documents(docs)

    print("\n3. Testing POST /api/v1/diagnose-and-advise...")
    payload = {
        "farmer_query": "عندي ندوة متاخرة في البطاطس، ايه علاجها وايه جرعة الرشاش؟",
        "region": "delta"
    }
    diag_res = requests.post("http://127.0.0.1:8080/api/v1/diagnose-and-advise", data=payload).json()
    print(f"   Intent: {diag_res['intent']}")
    print(f"   Answer: {diag_res['answer'][:120]}...")
    print(f"   Confidence: {diag_res['retrieval_confidence']}")
    print(f"   Review Flag: {diag_res['needs_agronomist_review']}")
    print(f"   Latency: {diag_res['latency_seconds']}s")

    print("\n✨ Live Integration Server Validation Completed Successfully!")
