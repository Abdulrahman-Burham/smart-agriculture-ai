"""MLOps Real-Time System Monitoring and Drift Detection Service."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional
from prometheus_client import Counter, Histogram, Gauge

logger = logging.getLogger(__name__)

# Prometheus Metrics Definitions
REQUEST_COUNT = Counter(
    "rag_requests_total",
    "Total RAG and CV pipeline requests processed",
    ["intent", "status"]
)

REQUEST_LATENCY = Histogram(
    "rag_request_latency_seconds",
    "Pipeline request end-to-end latency in seconds",
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
)

CONFIDENCE_GAUGE = Gauge(
    "rag_retrieval_confidence",
    "Latest retrieval confidence score"
)

AGRONOMIST_REVIEW_COUNTER = Counter(
    "rag_agronomist_review_total",
    "Total queries flagged for mandatory agronomist review"
)


class SystemMonitor:
    """Monitors live execution metrics, latency percentiles, and confidence drift."""

    def __init__(self):
        self.latency_samples: List[float] = []
        self.confidence_samples: List[float] = []

    def record_request(
        self,
        intent: str,
        latency_sec: float,
        confidence: float,
        needs_review: bool,
        status: str = "success",
    ) -> None:
        """Record live metric sample into Prometheus registries and internal sample buffers."""
        REQUEST_COUNT.labels(intent=intent, status=status).inc()
        REQUEST_LATENCY.observe(latency_sec)
        CONFIDENCE_GAUGE.set(confidence)

        if needs_review:
            AGRONOMIST_REVIEW_COUNTER.inc()

        self.latency_samples.append(latency_sec)
        self.confidence_samples.append(confidence)

    def get_summary_statistics(self) -> Dict[str, Any]:
        """Compute system summary metrics and percentiles."""
        if not self.latency_samples:
            return {
                "total_requests": 0,
                "avg_latency_sec": 0.0,
                "p95_latency_sec": 0.0,
                "avg_confidence": 0.0,
                "drift_alert": False,
            }

        sorted_lat = sorted(self.latency_samples)
        n = len(sorted_lat)
        p95_idx = int(n * 0.95)

        avg_conf = sum(self.confidence_samples) / max(1, len(self.confidence_samples))
        drift_alert = avg_conf < 0.45

        return {
            "total_requests": n,
            "avg_latency_sec": round(sum(sorted_lat) / n, 4),
            "p95_latency_sec": round(sorted_lat[min(p95_idx, n - 1)], 4),
            "avg_confidence": round(avg_conf, 4),
            "drift_alert": drift_alert,
        }
