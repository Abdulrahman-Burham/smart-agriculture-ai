"""End-to-End Acceptance Test Suite verifying CV + RAG + API Integration."""

from __future__ import annotations

import io
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check_endpoint():
    """Verify system readiness probe returns healthy status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["services"]["api_gateway"] == "online"
    assert data["services"]["rag_pipeline"] == "online"


def test_metrics_endpoint():
    """Verify Prometheus operational metrics endpoint exposes valid metrics."""
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "rag_requests_total" in response.text


def test_standalone_cv_prediction():
    """Verify Computer Vision disease classification endpoint."""
    fake_image = io.BytesIO(b"fake image bytes content for leaf sample")
    files = {"image": ("tomato_leaf.jpg", fake_image, "image/jpeg")}
    data = {"crop_hint": "tomato"}

    response = client.post("/api/v1/cv/predict", files=files, data=data)
    assert response.status_code == 200
    res = response.json()
    assert res["crop_type"] == "tomato"
    assert res["disease_label"] == "early_blight"
    assert res["confidence_score"] > 0.80


def test_end_to_end_diagnose_and_advise_with_image():
    """Verify full integration flow: Image + Query -> CV -> RAG -> Grounded Advice Payload."""
    fake_image = io.BytesIO(b"potato leaf image bytes")
    files = {"image": ("potato_leaf.jpg", fake_image, "image/jpeg")}
    data = {
        "farmer_query": "عندي ندوة متاخرة في البطاطس، ايه علاجها وايه جرعة الرشاش؟",
        "region": "delta",
    }

    response = client.post("/api/v1/diagnose-and-advise", files=files, data=data)
    assert response.status_code == 200
    res = response.json()

    assert res["status"] == "success"
    assert res["intent"] == "dosage_lookup"
    assert res["vision_prediction"] is not None
    assert res["vision_prediction"]["crop_type"] == "potato"
    assert res["vision_prediction"]["disease_label"] == "late_blight"
    assert len(res["answer"]) > 0
    assert "citations" in res
    assert "retrieval_confidence" in res
    assert res["latency_seconds"] < 3.0
