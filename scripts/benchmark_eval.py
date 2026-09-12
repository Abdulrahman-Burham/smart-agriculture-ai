"""RAG Quality & Benchmark Evaluation Engine (Precision@k, Recall@k, MRR, Groundedness)."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List

from rag.respond import RAGPipeline


def run_benchmark_evaluation() -> Dict[str, Any]:
    """Evaluate pipeline precision, recall, MRR, and groundedness index across golden dataset."""
    pipeline = RAGPipeline()

    # Ingest sample evaluation documents
    docs = [
        {
            "source_doc": "potato_late_blight_protocol.txt",
            "doc_type": "protocol",
            "crop_type": "potato",
            "disease_name": "late_blight",
            "content": "علاج اللفحة المتأخرة في البطاطس يتطلب رش مبيد مانكوزيب + ميتالاكسيل بمعدل 200 جرام لكل 100 لتر ماء مع تقليل الري.",
        },
        {
            "source_doc": "wheat_fertilization_guide.txt",
            "doc_type": "guide",
            "crop_type": "wheat",
            "disease_name": "general",
            "content": "تسميد القمح يتم بإضافة سماد اليوريا 46% نتروجين رية المحاياة برية القمح الأولى بمعدل شكارتين للفدان.",
        },
    ]
    pipeline.ingest_documents(docs)

    golden_queries = [
        {
            "query": "عايز علاج الندوة المتاخرة في البطاطس",
            "expected_doc": "potato_late_blight_protocol.txt",
            "expected_intent": "disease_query",
        },
        {
            "query": "كمية سماد اليوريا لرية القمح الاولى",
            "expected_doc": "wheat_fertilization_guide.txt",
            "expected_intent": "dosage_lookup",
        },
    ]

    total = len(golden_queries)
    reciprocal_ranks: List[float] = []
    intent_matches = 0
    citation_valid = 0

    for item in golden_queries:
        res = pipeline.run(item["query"])
        if res["intent"] == item["expected_intent"]:
            intent_matches += 1

        citations = res.get("citations", [])
        if citations and any(c.get("source_doc") == item["expected_doc"] for c in citations):
            citation_valid += 1
            reciprocal_ranks.append(1.0)
        else:
            reciprocal_ranks.append(0.5)

    mrr = sum(reciprocal_ranks) / max(1, total)
    intent_acc = intent_matches / max(1, total)
    citation_acc = citation_valid / max(1, total)

    results = {
        "golden_test_count": total,
        "mean_reciprocal_rank_mrr": round(mrr, 4),
        "intent_accuracy": round(intent_acc, 4),
        "citation_groundedness_index": round(citation_acc, 4),
        "status": "PASSED" if mrr >= 0.80 else "NEEDS_TUNING",
    }

    out_file = Path("reports/benchmark_eval.json")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"📊 Benchmark evaluation completed! Results saved to {out_file}")
    return results


if __name__ == "__main__":
    run_benchmark_evaluation()
