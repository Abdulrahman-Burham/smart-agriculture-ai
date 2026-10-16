"""Unit and Integration Tests for Agricultural Calculators, Followup Recovery, and Telegram Webhooks."""

from __future__ import annotations

import io
from fastapi.testclient import TestClient
from PIL import Image
import pytest

from app.main import app
from app.core.config import DEV_SECRET_KEY
from app.schemas.calculator import TankMixRequest, SalinityRequest
from app.services.agri_calculator_service import calculate_tank_mix, evaluate_water_salinity

from computer_vision.storage.image_repository import save_image_record

client = TestClient(app)


def test_calculate_tank_mix_single_pesticide():
    """Verify single pesticide dosage calculation with realistic Egyptian knapsack rates."""
    req = TankMixRequest(
        area_value=1.0,
        area_unit="feddan",
        tank_type="knapsack_20l",
        dosage_rate=200.0,
        dosage_unit="per_feddan",
        chemical_type="powder",
        crop_category="vegetable",
        product_name="أميستار",
        mode="area",
    )
    res = calculate_tank_mix(req)
    assert res.area_feddan == 1.0
    assert res.tank_capacity_liters == 20.0
    assert res.total_water_liters == 140.0
    assert res.total_chemical_amount == 200.0
    assert res.amount_per_tank == 28.57
    assert res.tanks_count_practical == 7
    assert any(w in res.amount_per_tank_practical for w in ("ملعقة", "ملعقتين", "ملاعق", "كوب", "جم", "جرام"))


def test_calculate_tank_mix_direct_single_tank():
    """Verify direct single knapsack tank filling mode (mode='tank')."""
    req = TankMixRequest(
        mode="tank",
        tanks_count=1,
        tank_type="knapsack_20l",
        dosage_rate=50.0,
        dosage_unit="per_100l",
        chemical_type="liquid",
        crop_category="vegetable",
        product_name="مبيد حشري سائل",
    )
    res = calculate_tank_mix(req)
    assert res.tank_capacity_liters == 20.0
    assert res.total_water_liters == 20.0
    assert res.amount_per_tank == 10.0
    assert res.total_chemical_amount == 10.0
    assert "سرنجة" in res.amount_per_tank_practical or "سم³" in res.amount_per_tank_practical


def test_calculate_tank_mix_barrel_200l():
    """Verify 200L standard barrel container calculation."""
    req = TankMixRequest(
        mode="tank",
        tanks_count=1,
        tank_type="motor_200l",
        dosage_rate=250.0,
        dosage_unit="per_100l",
        chemical_type="powder",
        crop_category="orchard",
        product_name="كبريت ميكروني",
    )
    res = calculate_tank_mix(req)
    assert res.tank_capacity_liters == 200.0
    assert res.total_water_liters == 200.0
    assert res.amount_per_tank == 500.0
    assert res.total_chemical_amount == 500.0
    assert "500" in res.amount_per_tank_practical or "كوب" in res.amount_per_tank_practical or "كيس" in res.amount_per_tank_practical


def test_calculate_tank_mix_incompatible_copper_amino():
    """Verify chemical incompatibility caution for Copper + Amino acids."""
    req = TankMixRequest(
        area_value=2.0,
        area_unit="feddan",
        tank_type="motor_600l",
        dosage_rate=250.0,
        dosage_unit="per_feddan",
        chemical_type="powder",
        crop_category="orchard",
        product_name="أوكسي كلورور النحاس",
        mix_partners=["أحماض أمينية"],
    )
    res = calculate_tank_mix(req)
    assert len(res.compatibility_warnings) > 0
    assert any("النحاس" in w for w in res.compatibility_warnings)


def test_calculate_tank_mix_incompatible_sulfur_oils():
    """Verify chemical incompatibility caution for Sulfur + Horticultural Oils."""
    req = TankMixRequest(
        area_value=1.0,
        area_unit="feddan",
        tank_type="knapsack_20l",
        dosage_rate=250.0,
        dosage_unit="per_feddan",
        chemical_type="liquid",
        crop_category="orchard",
        product_name="كبريت ميكروني سائل",
        mix_partners=["زيت شتوي معدني"],
    )
    res = calculate_tank_mix(req)
    assert len(res.compatibility_warnings) > 0
    assert any("الكبريت" in w or "احتراق" in w for w in res.compatibility_warnings)


def test_calculate_tank_mix_compatible_mix():
    """Verify safe verdict for compatible compounds without warnings."""
    req = TankMixRequest(
        area_value=1.0,
        area_unit="feddan",
        tank_type="knapsack_20l",
        dosage_rate=250.0,
        dosage_unit="per_feddan",
        chemical_type="powder",
        crop_category="vegetable",
        product_name="دايثين م45 (مانكوزيب)",
        mix_partners=["سماد ورقي عالي البوتاسيوم"],
    )
    res = calculate_tank_mix(req)
    assert len(res.compatibility_warnings) == 0


def test_evaluate_water_salinity_ppm_and_sensitive_crop():
    """Verify FAO 29 salinity threshold and yield loss on sensitive strawberries."""
    req = SalinityRequest(
        salinity_value=1600.0,
        salinity_unit="ppm",
        crop_name="فراولة",
        irrigation_method="تنقيط",
    )
    res = evaluate_water_salinity(req)
    assert res.tds_ppm == 1600.0
    assert pytest.approx(res.ec_dsm, 0.1) == 2.5
    assert res.yield_potential_percent < 70.0
    assert res.crop_tolerance_threshold_ec == 1.0
    assert res.is_critical_risk is True
    assert len(res.alleviation_protocol) > 0


def test_evaluate_water_salinity_tolerant_palm():
    """Verify date palm tolerance to elevated salinity."""
    req = SalinityRequest(
        salinity_value=3.0,
        salinity_unit="ec",
        crop_name="نخيل",
        irrigation_method="غمر",
    )
    res = evaluate_water_salinity(req)
    assert res.ec_dsm == 3.0
    assert res.tds_ppm == 1920.0
    # Date palm threshold is 4.0 dS/m, so at 3.0 dS/m productivity should be 100%
    assert res.yield_potential_percent == 100.0
    assert res.is_critical_risk is False


def test_tank_mix_api_endpoint():
    """Verify POST /api/calculator/tank-mix endpoint."""
    payload = {
        "area_value": 1.0,
        "area_unit": "feddan",
        "tank_type": "knapsack_20l",
        "dosage_rate": 60.0,
        "dosage_unit": "per_feddan",
        "chemical_type": "liquid",
        "crop_category": "vegetable",
        "product_name": "كوراجين",
    }
    resp = client.post("/api/calculator/tank-mix", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["area_feddan"] == 1.0
    assert data["total_chemical_amount"] == 60.0
    assert "amount_per_tank_practical" in data


def test_salinity_api_endpoint():
    """Verify POST /api/calculator/salinity endpoint."""
    payload = {
        "salinity_value": 960.0,
        "salinity_unit": "ppm",
        "crop_name": "طماطم",
        "irrigation_method": "تنقيط",
    }
    resp = client.post("/api/calculator/salinity", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["crop_name"] == "طماطم"
    assert data["ec_dsm"] == 1.5
    assert "evaluation_ar" in data


def test_offline_guide_page_endpoint():
    """Verify GET /offline-guide serves HTML correctly."""
    resp = client.get("/offline-guide")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "دليل الإسعافات" in resp.text
    assert "Abamectin" in resp.text
    assert "137" in resp.text


def test_telegram_config_endpoints_and_security():
    """Verify dev panel telegram configuration management with dev secret key."""
    # Without key -> 404 Not Found (Dev endpoints obscure their existence)
    unauth_resp = client.get("/api/dev/telegram-config")
    assert unauth_resp.status_code == 404

    # With key -> 200 OK
    auth_resp = client.get(f"/api/dev/telegram-config?key={DEV_SECRET_KEY}")
    assert auth_resp.status_code == 200
    cfg = auth_resp.json()
    assert "has_token" in cfg
    assert "chat_id" in cfg

    # Save telegram config
    post_resp = client.post(
        f"/api/dev/telegram-config?key={DEV_SECRET_KEY}",
        json={"bot_token": "mock_token_12345", "chat_id": "mock_chat_67890"},
    )
    assert post_resp.status_code == 200
    assert post_resp.json()["status"] == "success"

    # Test endpoint (mock token returns 200 if valid or 400 if mock credentials fail connection)
    test_resp = client.post(f"/api/dev/telegram-test?key={DEV_SECRET_KEY}&message=unit_test")
    assert test_resp.status_code in (200, 400)



def test_followup_recovery_evaluation_endpoint():
    """Verify POST /api/diagnose/followup compares baseline and followup images."""
    # Create baseline image record in DB
    img = Image.new("RGB", (224, 224), color="green")
    buf1 = io.BytesIO()
    img.save(buf1, format="JPEG")
    baseline_bytes = buf1.getvalue()

    baseline_id = save_image_record(
        image_bytes=baseline_bytes,
        filename="baseline_leaf.jpg",
        source_endpoint="/api/diagnose",
        model_used="EfficientNetV2B2",
        predicted_class="Tomato___Early_blight",
        confidence="91.0%",
        top_predictions=[{"class": "Tomato___Early_blight", "confidence": 0.91}],
        predicted_class_ar="ندوة مبكرة في الطماطم",
        user_id=1,
    )

    # Follow-up image (healthy green leaf)
    buf2 = io.BytesIO()
    img.save(buf2, format="JPEG")
    buf2.seek(0)

    files = {"followup_image": ("followup_leaf.jpg", buf2, "image/jpeg")}
    data = {
        "baseline_image_id": str(baseline_id),
        "days_elapsed": "7",
    }

    resp = client.post("/api/diagnose/followup", files=files, data=data)
    assert resp.status_code == 200
    result = resp.json()
    assert result["baseline_image_id"] == baseline_id
    assert result["days_elapsed"] == 7
    assert 0.0 <= result["recovery_score"] <= 100.0
    assert result["status"] == "success"
    assert result["recovery_status"] in ("healed", "recovering", "active", "degraded", "controlled")

    assert "advice" in result
    assert isinstance(result["should_repeat_spray"], bool)
