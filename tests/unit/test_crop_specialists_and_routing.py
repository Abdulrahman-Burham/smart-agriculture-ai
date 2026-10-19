"""Unit tests verifying Crop-Specific Disease Specialists & Dynamic Routing Registry."""

import io
from PIL import Image
import pytest
from fastapi.testclient import TestClient

from app.main import app
from computer_vision.inference.classifier import PlantDiseaseClassifier
from computer_vision.inference.crop_specialists import (
    EXPANDED_CROP_CATALOGUES,
    CORE_CROP_KEYWORDS,
    diagnose_expanded_crop,
    filter_predictions_by_crop,
    is_expanded_crop,
    normalize_crop_hint,
)

client = TestClient(app)


def _create_synthetic_green_leaf_bytes() -> bytes:
    """Create a realistic synthetic green image that passes the plant gatekeeper."""
    img = Image.new("RGB", (256, 256), color=(34, 139, 34))  # Forest green
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def test_normalize_crop_hint():
    """Verify crop aliases and normalizations."""
    assert normalize_crop_hint("طماطم") == "طماطم"
    assert normalize_crop_hint("tomato") == "طماطم"
    assert normalize_crop_hint("TOMATOES") == "طماطم"
    assert normalize_crop_hint("مانجا") == "مانجو"
    assert normalize_crop_hint("mango") == "مانجو"
    assert normalize_crop_hint("قمح") == "قمح"
    assert normalize_crop_hint("wheat") == "قمح"
    assert normalize_crop_hint("زيتون") == "زيتون"
    assert normalize_crop_hint("olive") == "زيتون"
    assert normalize_crop_hint("أرز") == "أرز"
    assert normalize_crop_hint("ارز") == "أرز"
    assert normalize_crop_hint("بصل") == "بصل"
    assert normalize_crop_hint("ثوم") == "بصل"
    assert normalize_crop_hint("موالح") == "موالح"
    assert normalize_crop_hint("برتقال") == "موالح"
    assert normalize_crop_hint("citrus") == "موالح"

    # Ignored / General / None values
    assert normalize_crop_hint(None) is None
    assert normalize_crop_hint("") is None
    assert normalize_crop_hint("عام") is None
    assert normalize_crop_hint("تلقائي") is None
    assert normalize_crop_hint("all") is None


def test_is_expanded_crop():
    """Verify check for expanded crops."""
    assert is_expanded_crop("مانجو") is True
    assert is_expanded_crop("قمح") is True
    assert is_expanded_crop("زيتون") is True
    assert is_expanded_crop("أرز") is True
    assert is_expanded_crop("بصل") is True

    # Core crops or invalid are False
    assert is_expanded_crop("طماطم") is False
    assert is_expanded_crop("بطاطس") is False
    assert is_expanded_crop("ذرة") is False
    assert is_expanded_crop(None) is False
    assert is_expanded_crop("unknown") is False


def test_diagnose_expanded_crop_mango():
    """Verify Mango specialist diagnosis."""
    # Signals indicating chlorosis/necrosis
    signals = {"green_foliage_pct": 10.0, "yellow_leaf_pct": 20.0, "exg_pct": 6.0}
    result = diagnose_expanded_crop("مانجو", signals)

    assert result["is_plant"] is True
    assert result["crop_type"] == "Mango"
    assert result["crop_type_ar"] == "مانجو"
    assert "Anthracnose" in result["predicted_class"]
    assert len(result["top_predictions"]) <= 3
    assert len(result["predictions"]) == 5
    assert result["confidence"] > 70.0


def test_diagnose_expanded_crop_wheat():
    """Verify Wheat specialist diagnosis."""
    # Signals indicating yellow rust stripes
    signals = {"green_foliage_pct": 20.0, "yellow_leaf_pct": 18.0, "exg_pct": 15.0}
    result = diagnose_expanded_crop("قمح", signals)

    assert result["is_plant"] is True
    assert result["crop_type"] == "Wheat"
    assert result["crop_type_ar"] == "قمح"
    assert "Yellow_rust" in result["predicted_class"]
    assert "الصدأ الأصفر" in result["predicted_class_ar"]


def test_filter_predictions_by_crop_renormalization():
    """Verify crop-aware probability isolation on unified predictions."""
    sample_preds = [
        {"class": "Tomato___Early_blight", "label_ar": "طماطم — اللفحة المبكرة", "confidence": 0.40},
        {"class": "Tomato___healthy", "label_ar": "طماطم — سليم", "confidence": 0.10},
        {"class": "Potato___Late_blight", "label_ar": "بطاطس — اللفحة المتأخرة", "confidence": 0.30},
        {"class": "Pepper,_bell___Bacterial_spot", "label_ar": "فلفل حلو — التبقع البكتيري", "confidence": 0.20},
    ]

    # Filter for Tomato
    top_3, detailed = filter_predictions_by_crop(sample_preds, "طماطم")
    assert len(detailed) == 2
    assert all("Tomato" in p["class"] for p in detailed)
    # 0.40 / (0.40 + 0.10) = 0.80 -> 80%
    assert detailed[0]["class"] == "Tomato___Early_blight"
    assert detailed[0]["confidence_percent"] == 80.0
    # 0.10 / (0.40 + 0.10) = 0.20 -> 20%
    assert detailed[1]["confidence_percent"] == 20.0

    # Filter for Potato
    top_3_p, detailed_p = filter_predictions_by_crop(sample_preds, "بطاطس")
    assert len(detailed_p) == 1
    assert detailed_p[0]["class"] == "Potato___Late_blight"
    assert detailed_p[0]["confidence_percent"] == 100.0


def test_classifier_predict_with_expanded_crop_hint():
    """Verify PlantDiseaseClassifier routes to expanded specialist when hint provided."""
    classifier = PlantDiseaseClassifier()
    img_bytes = _create_synthetic_green_leaf_bytes()

    # Pass mango hint
    result = classifier.predict(img_bytes, top_k=3, crop_hint="مانجو")
    assert result["is_plant"] is True
    assert result["crop_type"] == "Mango"
    assert result["crop_type_ar"] == "مانجو"
    assert "Mango" in result["predicted_class"]
    assert "Specialist_Mango_Model" in result["model_used"]

    # Pass wheat hint
    result_wheat = classifier.predict(img_bytes, top_k=3, crop_hint="قمح")
    assert result_wheat["is_plant"] is True
    assert result_wheat["crop_type"] == "Wheat"
    assert result_wheat["crop_type_ar"] == "قمح"
    assert "Wheat" in result_wheat["predicted_class"]


def test_api_diagnose_with_crop_parameter():
    """Verify POST /api/diagnose handles crop form field cleanly."""
    img_bytes = _create_synthetic_green_leaf_bytes()
    files = {"image": ("wheat_leaf.jpg", img_bytes, "image/jpeg")}
    data = {
        "query": "ما هو المرض في القمح وكيف نعالجه؟",
        "crop": "قمح",
    }

    response = client.post("/api/diagnose", files=files, data=data)
    assert response.status_code == 200
    res = response.json()
    assert res["is_plant"] is True
    cv = res.get("cv_result", {})
    assert cv.get("crop_type_ar") == "قمح"
    assert "advice" in res
    assert len(res["advice"]) > 0
