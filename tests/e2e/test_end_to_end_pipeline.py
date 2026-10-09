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


def test_standalone_cv_prediction():
    """Verify Computer Vision disease classification endpoint."""
    from computer_vision.standalone_cv_api import app as cv_app
    cv_client = TestClient(cv_app)
    
    # Create fake image with 3 channels
    import io
    from PIL import Image
    img = Image.new("RGB", (224, 224), color="green")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    
    files = {"file": ("tomato_leaf.jpg", buf, "image/jpeg")}
    response = cv_client.post("/predict", files=files)
    assert response.status_code == 200
    res = response.json()
    assert res["status"] == "success"
    assert "predictions" in res
    assert len(res["predictions"]) > 0


def test_end_to_end_diagnose_and_advise_with_image():
    """Verify full integration flow: Image + Query -> CV -> RAG -> Grounded Advice Payload."""
    import io
    from PIL import Image
    img = Image.new("RGB", (224, 224), color="green")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)

    files = {"image": ("potato_leaf.jpg", buf, "image/jpeg")}
    data = {
        "query": "عندي ندوة متاخرة في البطاطس، ايه علاجها وايه جرعة الرشاش؟",
    }

    response = client.post("/api/diagnose", files=files, data=data)
    assert response.status_code == 200
    res = response.json()

    assert "cv_result" in res
    assert "advice" in res
    assert "confidence" in res
    assert res["latency"] >= 0
