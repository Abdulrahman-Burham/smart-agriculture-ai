from __future__ import annotations

import math

from ..nlp.arabic import normalize_arabic


def hit_at_k(retrieved_sources: list[str], expected: list[str], k: int) -> float:
    return 1.0 if set(retrieved_sources[:k]) & set(expected) else 0.0


def reciprocal_rank(retrieved_sources: list[str], expected: list[str]) -> float:
    for i, src in enumerate(retrieved_sources, start=1):
        if src in expected:
            return 1.0 / i
    return 0.0


def keyword_recall(answer: str, keywords: list[str]) -> float:
    if not keywords:
        return 1.0
    norm = normalize_arabic(answer)
    return sum(normalize_arabic(k) in norm for k in keywords) / len(keywords)


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = max(0, min(len(ordered) - 1, math.ceil(pct / 100 * len(ordered)) - 1))
    return ordered[idx]


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def suggest_threshold(in_scope_top: list[float], out_scope_top: list[float]) -> float | None:
    """Midpoint between the weakest in-scope and strongest out-of-scope top similarity."""
    if not in_scope_top or not out_scope_top:
        return None
    lo, hi = min(in_scope_top), max(out_scope_top)
    return round((lo + hi) / 2, 3) if lo > hi else round(hi + 0.01, 3)
