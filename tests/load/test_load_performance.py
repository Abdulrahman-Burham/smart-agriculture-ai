"""Load and Stress Performance Testing Script for System Monitoring & Load Stability."""

from __future__ import annotations

import io
import time
from typing import Any, Dict, List
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def run_load_stress_test(num_requests: int = 50) -> Dict[str, Any]:
    """Simulate concurrent farmer queries and measure system stability and SLA compliance."""
    latencies: List[float] = []
    successes = 0
    failures = 0

    queries = [
        ("عندي ندوة متاخرة في البطاطس، ايه علاجها وايه جرعة الرشاش؟", "potato"),
        ("ما هي مواعيد تسميد اليوريا محصول القمح؟", "wheat"),
        ("اعراض البياض الدقيقي في الخيار وطريقة الوقاية", "cucumber"),
        ("متى يفضل ري الطماطم في الجو الحر؟", "tomato"),
    ]

    start_total = time.time()

    for idx in range(num_requests):
        query_text, crop_hint = queries[idx % len(queries)]
        fake_image = io.BytesIO(f"sample leaf bytes {idx}".encode("utf-8"))
        files = {"image": (f"{crop_hint}_leaf_{idx}.jpg", fake_image, "image/jpeg")}
        data = {"farmer_query": query_text, "crop_override": crop_hint}

        req_start = time.time()
        try:
            response = client.post("/api/v1/diagnose-and-advise", files=files, data=data)
            latency = time.time() - req_start
            latencies.append(latency)

            if response.status_code == 200:
                successes += 1
            else:
                failures += 1
        except Exception as err:
            failures += 1
            latencies.append(time.time() - req_start)

    total_duration = time.time() - start_total
    sorted_lat = sorted(latencies)
    n = len(sorted_lat)

    p50 = sorted_lat[int(n * 0.50)] if n > 0 else 0.0
    p95 = sorted_lat[int(n * 0.95)] if n > 0 else 0.0
    p99 = sorted_lat[int(n * 0.99)] if n > 0 else 0.0
    rps = num_requests / max(0.001, total_duration)

    sla_passed = p95 < 3.0 and failures == 0

    return {
        "num_requests": num_requests,
        "successes": successes,
        "failures": failures,
        "total_duration_sec": round(total_duration, 4),
        "requests_per_sec": round(rps, 2),
        "p50_latency_sec": round(p50, 4),
        "p95_latency_sec": round(p95, 4),
        "p99_latency_sec": round(p99, 4),
        "sla_target_passed": sla_passed,
    }


if __name__ == "__main__":
    print("⚡ Running System Load & Stability Performance Test...")
    res = run_load_stress_test(num_requests=50)
    print(f"✅ Executed {res['num_requests']} requests in {res['total_duration_sec']}s ({res['requests_per_sec']} RPS)")
    print(f"📊 Latency Percentiles: p50={res['p50_latency_sec']}s, p95={res['p95_latency_sec']}s, p99={res['p99_latency_sec']}s")
    print(f"🎯 SLA Compliance Target (<3.0s): {'PASSED' if res['sla_target_passed'] else 'FAILED'}")
