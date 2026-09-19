"""Run the RAG pipeline over uploaded PDFs and evaluate a golden question set."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

# Allow this script to be launched directly from the repository root.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from rag.respond import RAGPipeline


def load_questions(path: Path) -> list[dict[str, Any]]:
    questions = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON on line {line_number} of {path}: {exc}") from exc
        if not item.get("query"):
            raise ValueError(f"Question on line {line_number} must include 'query'.")
        questions.append(item)
    return questions


def evaluate(pipeline: RAGPipeline, questions: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for item in questions:
        started = time.perf_counter()
        result = pipeline.run(item["query"])
        latency = time.perf_counter() - started
        sources = {citation.get("source_doc") for citation in result.get("citations", [])}
        expected_source = item.get("expected_source")
        keywords = [str(word).lower() for word in item.get("expected_keywords", [])]
        answer = result.get("answer", "").lower()
        keyword_score = (
            sum(keyword in answer for keyword in keywords) / len(keywords)
            if keywords
            else None
        )
        rows.append(
            {
                "query": item["query"],
                "answer": result["answer"],
                "citations": result.get("citations", []),
                "retrieval_confidence": result.get("retrieval_confidence", 0.0),
                "intent": result.get("intent"),
                "expected_intent": item.get("expected_intent"),
                "intent_match": (
                    result.get("intent") == item["expected_intent"]
                    if item.get("expected_intent")
                    else None
                ),
                "source_hit": expected_source in sources if expected_source else None,
                "keyword_coverage": keyword_score,
                "needs_agronomist_review": result.get("needs_agronomist_review"),
                "latency_seconds": round(latency, 4),
            }
        )

    def average(field: str) -> float | None:
        values = [row[field] for row in rows if row[field] is not None]
        return round(sum(values) / len(values), 4) if values else None

    source_hits = [row["source_hit"] for row in rows if row["source_hit"] is not None]
    intent_matches = [row["intent_match"] for row in rows if row["intent_match"] is not None]
    review_flags = [row["needs_agronomist_review"] for row in rows]
    matrix = {
        "question_count": len(rows),
        "retrieval_source_hit_rate": round(sum(source_hits) / len(source_hits), 4)
        if source_hits
        else None,
        "intent_accuracy": round(sum(intent_matches) / len(intent_matches), 4)
        if intent_matches
        else None,
        "answer_keyword_coverage": average("keyword_coverage"),
        "mean_retrieval_confidence": average("retrieval_confidence"),
        "mean_latency_seconds": average("latency_seconds"),
        "review_flag_rate": round(sum(review_flags) / len(review_flags), 4) if rows else 0.0,
        "results": rows,
    }
    return matrix


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", action="append", type=Path, help="PDF file; repeat for multiple files.")
    parser.add_argument("--pdf-dir", type=Path, help="Recursively ingest all PDFs in this directory.")
    parser.add_argument("--questions", type=Path, help="JSONL golden questions for evaluation.")
    parser.add_argument("--report", type=Path, default=Path("reports/uploaded_rag_eval.json"))
    parser.add_argument("--ask", action="store_true", help="Open an interactive Arabic question loop.")
    args = parser.parse_args()

    pdfs = list(args.pdf or [])
    if args.pdf_dir:
        pdfs.extend(sorted(args.pdf_dir.rglob("*.pdf")))
    pdfs = sorted({path.resolve() for path in pdfs})
    if not pdfs:
        parser.error("Provide --pdf or --pdf-dir.")
    missing = [path for path in pdfs if not path.is_file()]
    if missing:
        parser.error("Missing PDF files: " + ", ".join(map(str, missing)))

    pipeline = RAGPipeline()
    summary = pipeline.ingest_pdfs([str(path) for path in pdfs])
    print(json.dumps({"ingestion": summary}, ensure_ascii=False, indent=2))

    if args.questions:
        report = evaluate(pipeline, load_questions(args.questions))
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({key: value for key, value in report.items() if key != "results"}, ensure_ascii=False, indent=2))
        print(f"Evaluation report: {args.report}")

    if args.ask:
        print("اكتب سؤالك بالعربي، أو اكتب exit للخروج.")
        for question in sys.stdin:
            question = question.strip()
            if question.lower() in {"exit", "quit", "خروج"}:
                break
            if not question:
                continue
            result = pipeline.run(question)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            print("---")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
