"""Evaluation harness (the 'answer accuracy evaluation protocol' deliverable).

    python -m agri_rag.evaluation.run --retrieval-only          # no API key needed
    python -m agri_rag.evaluation.run --judge                   # full end-to-end + LLM judge

Measures, per the project KPIs:
  * Retrieval  : Hit@k, MRR, dense similarity distribution (-> threshold calibration)
  * Answers    : keyword recall, citation rate, refusal correctness on out-of-scope questions,
                 optional LLM-as-judge faithfulness / relevance (1-5)
  * Latency    : retrieval, time-to-first-token, total (p50/p95) vs the 3 s budget
"""
from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime
from pathlib import Path

from ..config import ROOT, get_settings
from ..container import Container, build_container
from .metrics import hit_at_k, keyword_recall, mean, percentile, reciprocal_rank, suggest_threshold

JUDGE_SYSTEM = (
    "You are a strict agronomy evaluator. Given SOURCES, a QUESTION and an ANSWER, return ONLY JSON: "
    '{"faithfulness": 1-5, "relevance": 1-5, "unsupported_claims": ["..."]}. '
    "faithfulness=5 only if every factual claim (numbers, products, doses) is supported by SOURCES."
)


def load_golden(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


async def _judge(c: Container, question: str, answer: str, sources: list[dict]) -> dict | None:
    body = "SOURCES:\n" + "\n---\n".join(s["snippet"] for s in sources) + f"\n\nQUESTION: {question}\n\nANSWER: {answer}"
    raw = await c.llm.complete(JUDGE_SYSTEM, [{"role": "user", "content": body}], max_tokens=300)
    try:
        return json.loads(raw[raw.index("{"): raw.rindex("}") + 1])
    except (ValueError, json.JSONDecodeError):
        return None


async def evaluate(c: Container, golden: list[dict], k: int, retrieval_only: bool, judge: bool) -> dict:
    rows: list[dict] = []
    for item in golden:
        row = {"id": item["id"], "question": item["question"], "in_scope": item["in_scope"]}
        if retrieval_only:
            res = await asyncio.to_thread(c.retriever.retrieve, item["question"], item.get("crop"), k)
            sources = [ch.metadata["source"] for ch in res.chunks]
            row["top_similarity"] = res.top_similarity
        else:
            r = await c.pipeline.ask(item["question"], crop=item.get("crop"))
            sources = [s["source"] for s in r.sources]
            row.update(answer=r.answer, grounded=r.grounded, timings=r.timings, cited=bool(r.cited_ids),
                       top_similarity=max((s["similarity"] or 0 for s in r.sources), default=0.0))
            if item["in_scope"]:
                row["keyword_recall"] = keyword_recall(r.answer, item["expected_keywords"])
                if judge:
                    row["judge"] = await _judge(c, item["question"], r.answer, r.sources)
        if item["in_scope"]:
            row["hit_at_k"] = hit_at_k(sources, item["expected_sources"], k)
            row["rr"] = reciprocal_rank(sources, item["expected_sources"])
        row["retrieved"] = sources
        rows.append(row)

    ins = [r for r in rows if r["in_scope"]]
    outs = [r for r in rows if not r["in_scope"]]
    summary: dict = {
        "n_in_scope": len(ins), "n_out_of_scope": len(outs), "k": k,
        f"hit@{k}": round(mean([r["hit_at_k"] for r in ins]), 3),
        "mrr": round(mean([r["rr"] for r in ins]), 3),
        "suggested_min_similarity": suggest_threshold([r["top_similarity"] for r in ins],
                                                      [r["top_similarity"] for r in outs]),
        "current_min_similarity": c.settings.min_similarity,
    }
    if not retrieval_only:
        ttft = [r["timings"]["ttft_ms"] for r in rows]
        total = [r["timings"]["total_ms"] for r in rows]
        summary.update({
            "keyword_recall": round(mean([r["keyword_recall"] for r in ins]), 3),
            "citation_rate": round(mean([1.0 if r["cited"] else 0.0 for r in ins if r["grounded"]]), 3),
            "refusal_accuracy_oos": round(mean([0.0 if r["grounded"] else 1.0 for r in outs]), 3),
            "ttft_ms_p50": percentile(ttft, 50), "ttft_ms_p95": percentile(ttft, 95),
            "total_ms_p50": percentile(total, 50), "total_ms_p95": percentile(total, 95),
            "latency_budget_ms": int(c.settings.latency_budget_s * 1000),
            "within_budget_rate": round(mean([1.0 if r["timings"]["within_budget"] else 0.0 for r in rows]), 3),
        })
        judged = [r["judge"] for r in ins if r.get("judge")]
        if judged:
            summary["judge_faithfulness"] = round(mean([j["faithfulness"] for j in judged]), 2)
            summary["judge_relevance"] = round(mean([j["relevance"] for j in judged]), 2)
    return {"generated_at": datetime.now().isoformat(timespec="seconds"), "summary": summary, "rows": rows}


def to_markdown(report: dict) -> str:
    lines = ["# تقرير تقييم المساعد الزراعي (RAG)", f"_تاريخ التشغيل: {report['generated_at']}_", "",
             "## الملخص", "| المقياس | القيمة |", "|---|---|"]
    lines += [f"| {k} | {v} |" for k, v in report["summary"].items()]
    lines += ["", "## تفاصيل الأسئلة", "| id | نطاق | hit@k | RR | أعلى تشابه | المصادر المسترجعة |", "|---|---|---|---|---|---|"]
    for r in report["rows"]:
        lines.append(f"| {r['id']} | {'داخل' if r['in_scope'] else 'خارج'} | {r.get('hit_at_k', '-')} | "
                     f"{round(r.get('rr', 0), 2) if 'rr' in r else '-'} | {round(r['top_similarity'], 3)} | "
                     f"{', '.join(dict.fromkeys(r['retrieved']))} |")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--golden", default=str(ROOT / "data" / "eval" / "golden_set.jsonl"))
    ap.add_argument("--k", type=int, default=3)
    ap.add_argument("--retrieval-only", action="store_true")
    ap.add_argument("--judge", action="store_true")
    ap.add_argument("--out", default=str(ROOT / "reports"))
    args = ap.parse_args()
    c = build_container(get_settings())
    report = asyncio.run(evaluate(c, load_golden(Path(args.golden)), args.k, args.retrieval_only, args.judge))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "eval_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "eval_report.md").write_text(to_markdown(report), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
