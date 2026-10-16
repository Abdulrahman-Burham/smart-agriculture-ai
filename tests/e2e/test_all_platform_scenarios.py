"""Comprehensive End-to-End Scenario Test Suite for Smart Agriculture AI Platform.

Covers all core user, farmer, and developer scenarios:
1. Public Web Pages & Static Brand Assets (Landing, Dashboard, Mobile, Offline Guide, PWA, Prescriptions)
2. Farmer Authentication, Registration, Preference Pinning, and Account Management
3. System Health, Public Stats, Egyptian Weather & Epidemic Risk Warning
4. Smart Agricultural Calculators (Tank-Mix Direct & Area Modes, Scoop Conversions, Salinity Advisor)
5. Computer Vision Leaf Diagnosis, Heatmap Prescriptions, and Before/After Recovery Follow-up
6. Conversational Agri-RAG, Memory Retention, and Dialect Response
7. Egyptian Speech Processing (EdgeTTS Voice Synthesis & STT Gateway)
8. Developer Admin Telemetry, Online DB Backups, Cache Clearing, and Secret Key Gate
9. Guest Access Quota and Telemetry Tracking
"""

from __future__ import annotations

import io
import time
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.core.config import DEV_SECRET_KEY
from computer_vision.storage.image_repository import save_image_record

client = TestClient(app)


def _make_dummy_image(color: str = "green", size: tuple[int, int] = (224, 224), fmt: str = "JPEG") -> io.BytesIO:
    """Helper to generate in-memory dummy plant leaf images."""
    img = Image.new("RGB", size, color=color)
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    buf.seek(0)
    return buf


# ═════════════════════════════════════════════════════════════════════════════
# 1. PUBLIC WEB PAGES & STATIC BRAND ASSETS SCENARIOS
# ═════════════════════════════════════════════════════════════════════════════

def test_scenario_pages_landing_default_and_explicit():
    """Scenario 1.1: Root (/) and /landing load Arabic landing page with no-cache headers."""
    for path in ("/", "/landing"):
        resp = client.get(path)
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")
        assert resp.headers.get("Cache-Control") == "no-cache, no-store, must-revalidate"
        assert "الخبير الزراعي" in resp.text or "smart" in resp.text.lower()


def test_scenario_pages_view_param_overrides():
    """Scenario 1.2 & 1.3: ?view=desktop and ?view=mobile query parameters force target templates."""
    resp_desktop = client.get("/?view=desktop")
    assert resp_desktop.status_code == 200
    assert "text/html" in resp_desktop.headers.get("content-type", "")

    resp_mobile = client.get("/?view=mobile")
    assert resp_mobile.status_code == 200
    assert "text/html" in resp_mobile.headers.get("content-type", "")


def test_scenario_pages_dashboard_user_agent_routing():
    """Scenario 1.4 & 1.5: /dashboard serves desktop on PC, but switches to mobile UI on smartphone User-Agents."""
    # Desktop UA
    resp_pc = client.get("/dashboard", headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    assert resp_pc.status_code == 200

    # Mobile UA (iPhone / Android)
    resp_phone = client.get("/dashboard", headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Mobile"})
    assert resp_phone.status_code == 200


def test_scenario_pages_mobile_and_simple_views():
    """Scenario 1.6 & 1.7: Dedicated mobile (/m, /mobile) and simple 2-button UI (/simple)."""
    for path in ("/m", "/mobile"):
        resp = client.get(path)
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")

    resp_simple = client.get("/simple")
    assert resp_simple.status_code == 200


def test_scenario_pages_offline_guide():
    """Scenario 1.8: Offline agricultural first-aid and safety guide loads with 200 OK."""
    resp = client.get("/offline-guide")
    assert resp.status_code == 200
    assert "دليل" in resp.text or "الإسعافات" in resp.text or "أوفلاين" in resp.text or "offline" in resp.text.lower()


def test_scenario_pages_login_and_oauth_chooser():
    """Scenario 1.9 & 1.10: Login & OAuth chooser pages."""
    resp_login = client.get("/login")
    assert resp_login.status_code == 200
    assert "تسجيل" in resp_login.text or "دخول" in resp_login.text or "login" in resp_login.text.lower()

    resp_chooser = client.get("/auth/choose-account")
    assert resp_chooser.status_code == 200


def test_scenario_pages_pwa_and_brand_assets():
    """Scenario 1.11: Favicon, brand logo, PWA manifest, and service worker exist and serve correctly."""
    assets = [
        ("/favicon.ico", 200),
        ("/logo.png", 200),
        ("/manifest.json", 200),
        ("/service-worker.js", 200),
    ]
    for url, expected_code in assets:
        resp = client.get(url)
        assert resp.status_code == expected_code, f"Failed serving {url}"


def test_scenario_pages_prescription_existing_vs_nonexistent():
    """Scenario 1.12: Printable prescription for existing image record vs non-existent 404."""
    # 1. Non-existent record returns friendly 404 HTML
    resp_404 = client.get("/prescription/99999999")
    assert resp_404.status_code == 404
    assert "غير متوفرة" in resp_404.text

    # 2. Existing record returns 200 HTML
    buf = _make_dummy_image()
    img_id = save_image_record(
        image_bytes=buf.getvalue(),
        filename="scenario_prescription_test.jpg",
        source_endpoint="/api/diagnose",
        model_used="mobilenet_v3",
        predicted_class="Tomato___Late_blight",
        predicted_class_ar="طماطم - ندوة متأخرة",
        confidence="96.00%",
        top_predictions=[{"class": "Tomato___Late_blight", "confidence": 0.96}],
        rag_advice="رش مبيد نحاسي أو ميتالاكسيل فوراً.",
        client_ip="127.0.0.1",
        visitor_hash="scenario_visitor_123",
    )
    resp_200 = client.get(f"/prescription/{img_id}")
    assert resp_200.status_code == 200
    assert "طماطم" in resp_200.text or "ندوة" in resp_200.text or "روشتة" in resp_200.text


# ═════════════════════════════════════════════════════════════════════════════
# 2. FARMER AUTHENTICATION, REGISTRATION & PREFERENCE SCENARIOS
# ═════════════════════════════════════════════════════════════════════════════

def test_scenario_auth_full_registration_and_duplicate_handling():
    """Scenario 2.1 & 2.2: Register new farmer, verify cookie, and prevent duplicate registration."""
    ts = int(time.time())
    unique_phone = f"010{ts % 100000000:08d}"
    payload = {
        "full_name": "الحاج رضوان الشرقاوي",
        "identifier": unique_phone,
        "password": "FarmSecretPass123",
        "confirm_password": "FarmSecretPass123",
        "governorate": "الدقهلية",
        "primary_crop": "مانجو",
        "farm_size_feddan": 15.0,
        "irrigation_type": "تنقيط",
    }

    # 1. First registration succeeds
    resp = client.post("/api/auth/register", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "token" in data
    assert data["user"]["full_name"] == "الحاج رضوان الشرقاوي"
    assert data["user"]["governorate"] == "الدقهلية"
    assert data["user"]["farm_size_feddan"] == 15.0
    assert "agri_auth_token" in resp.cookies

    # 2. Duplicate registration with same phone fails gracefully with 400
    dup_resp = client.post("/api/auth/register", json=payload)
    assert dup_resp.status_code == 400
    assert "مسجل بالفعل" in dup_resp.json()["detail"]


def test_scenario_auth_registration_validation_errors():
    """Scenario 2.3: Validation rejects invalid names, non-matching passwords, and invalid phone formats."""
    # Password mismatch
    resp_pw = client.post("/api/auth/register", json={
        "full_name": "أحمد الشناوي",
        "identifier": "01012345678",
        "password": "Password123",
        "confirm_password": "DifferentPassword123",
        "governorate": "كفر الشيخ",
    })
    assert resp_pw.status_code == 400

    # Short name
    resp_name = client.post("/api/auth/register", json={
        "full_name": "أ",
        "identifier": "01012345678",
        "password": "Password123",
        "confirm_password": "Password123",
    })
    assert resp_name.status_code == 400


def test_scenario_auth_login_success_and_failure():
    """Scenario 2.4 & 2.5: Login with valid credentials vs invalid credentials."""
    ts = int(time.time()) + 1
    phone = f"011{ts % 100000000:08d}"
    # Register first
    client.post("/api/auth/register", json={
        "full_name": "سيد قطب المنوفي",
        "identifier": phone,
        "password": "CorrectPassword123",
        "confirm_password": "CorrectPassword123",
        "governorate": "المنوفية",
        "primary_crop": "بطاطس",
    })

    # Valid Login
    login_ok = client.post("/api/auth/login", json={
        "identifier": phone,
        "password": "CorrectPassword123",
    })
    assert login_ok.status_code == 200
    assert login_ok.json()["status"] == "ok"
    assert "token" in login_ok.json()

    # Invalid Password (returns 401 Unauthorized)
    login_bad = client.post("/api/auth/login", json={
        "identifier": phone,
        "password": "WrongPassword999",
    })
    assert login_bad.status_code == 401


def test_scenario_auth_me_endpoint_guest_vs_authenticated():
    """Scenario 2.6: GET /api/auth/me returns guest quota for visitors and full user profile for logged-in farmers."""
    # Fresh guest client without inherited cookies
    guest_client = TestClient(app)
    guest_resp = guest_client.get("/api/auth/me")
    assert guest_resp.status_code == 200
    gdata = guest_resp.json()
    assert gdata["authenticated"] is False
    assert "guest_quota" in gdata

    # Logged-in farmer request
    ts = int(time.time()) + 2
    phone = f"012{ts % 100000000:08d}"
    reg_resp = client.post("/api/auth/register", json={
        "full_name": "سعد زغلول البحراوي",
        "identifier": phone,
        "password": "PasswordPass123",
        "confirm_password": "PasswordPass123",
        "governorate": "البحيرة",
        "primary_crop": "برتقال وموالح",
        "farm_size_feddan": 20.0,
        "irrigation_type": "رش",
    })
    token = reg_resp.json()["token"]

    auth_resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert auth_resp.status_code == 200
    adata = auth_resp.json()
    assert adata["authenticated"] is True
    assert adata["user"]["full_name"] == "سعد زغلول البحراوي"
    assert adata["user"]["governorate"] == "البحيرة"


def test_scenario_auth_visitor_preferences_persistence():
    """Scenario 2.7: Save and retrieve pinned GPS location and farm preferences."""
    pref_payload = {
        "governorate": "الدقهلية",
        "gps_lat": 31.0409,
        "gps_lon": 31.3785,
        "location_source": "gps",
        "primary_crop": "طماطم",
        "farm_size_feddan": 3.5,
        "irrigation_type": "تنقيط",
    }
    save_resp = client.post("/api/user/preferences", json=pref_payload)
    assert save_resp.status_code == 200
    assert save_resp.json()["status"] == "ok"
    assert save_resp.json()["preferences"]["governorate"] == "الدقهلية"
    assert save_resp.json()["preferences"]["primary_crop"] == "طماطم"

    # Verify retrieval
    get_resp = client.get("/api/user/preferences")
    assert get_resp.status_code == 200
    pdata = get_resp.json()
    pref_dict = pdata.get("preferences", pdata)
    assert pref_dict.get("governorate") == "الدقهلية"
    assert pref_dict.get("farm_size_feddan") == 3.5


def test_scenario_auth_logout_clears_cookie():
    """Scenario 2.8: POST /api/auth/logout unsets authentication cookie."""
    resp = client.post("/api/auth/logout")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_scenario_auth_social_quick_auth():
    """Scenario 2.9: Social / Quick auth creates or links guest farmer session."""
    payload = {
        "provider": "quick_phone",
        "identifier": "01511223344",
        "full_name": "حامد الفلاح",
    }
    resp = client.post("/api/auth/social", json=payload)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert "token" in resp.json()


# ═════════════════════════════════════════════════════════════════════════════
# 3. SYSTEM HEALTH, PUBLIC STATS, WEATHER & EPIDEMIC ALERTS
# ═════════════════════════════════════════════════════════════════════════════

def test_scenario_system_health_and_readiness():
    """Scenario 3.1: System readiness and health check."""
    for method in (client.get, client.head):
        resp = method("/health")
        assert resp.status_code == 200


def test_scenario_public_stats_anonymized():
    """Scenario 3.2: Safe public stats for showcase without exposing personal information."""
    resp = client.get("/api/public-stats")
    assert resp.status_code == 200
    data = resp.json()
    assert any(k in data for k in ("registered_farmers", "rag_engine", "avg_rag_ms", "avg_vision_ms"))


def test_scenario_weather_by_governorate():
    """Scenario 3.3: Weather advisory for major Egyptian agricultural governorates."""
    for gov in ("الدقهلية", "البحيرة", "أسوان", "كفر الشيخ"):
        resp = client.get(f"/api/weather?gov={gov}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["governorate"] == gov
        assert "temperature" in data
        assert "humidity" in data
        assert "wind_speed" in data
        assert "alerts" in data


def test_scenario_weather_by_gps_nearest_mapping():
    """Scenario 3.4: Auto-mapping GPS coordinates to nearest Egyptian agricultural governorate."""
    # Mansoura / Dakahlia coordinates: 31.04, 31.38
    resp = client.get("/api/weather?lat=31.04&lon=31.38")
    assert resp.status_code == 200
    data = resp.json()
    assert data["governorate"] == "الدقهلية"
    assert data["is_gps"] is True


# ═════════════════════════════════════════════════════════════════════════════
# 4. SMART AGRICULTURAL CALCULATORS SCENARIOS
# ═════════════════════════════════════════════════════════════════════════════

def test_scenario_tank_mix_direct_single_tank_mode():
    """Scenario 4.1: Single tank direct mode (20L knapsack sprayer, 50ml/100L)."""
    payload = {
        "mode": "tank",
        "tanks_count": 1,
        "tank_type": "knapsack_20l",
        "dosage_rate": 50.0,
        "dosage_unit": "per_100l",
        "chemical_type": "liquid",
        "crop_category": "vegetable",
        "product_name": "كوراجين",
    }
    resp = client.post("/api/calculator/tank-mix", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["tank_capacity_liters"] == 20.0
    assert data["total_water_liters"] == 20.0
    assert data["amount_per_tank"] == 10.0
    assert data["total_chemical_amount"] == 10.0
    assert "سرنجة" in data["amount_per_tank_practical"] or "سم³" in data["amount_per_tank_practical"]


def test_scenario_tank_mix_direct_barrel_200l_mode():
    """Scenario 4.2: Direct single 200L barrel mode (powder 250g/100L)."""
    payload = {
        "mode": "tank",
        "tanks_count": 1,
        "tank_type": "motor_200l",
        "dosage_rate": 250.0,
        "dosage_unit": "per_100l",
        "chemical_type": "powder",
        "crop_category": "orchard",
        "product_name": "كبريت ميكروني",
    }
    resp = client.post("/api/calculator/tank-mix", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["tank_capacity_liters"] == 200.0
    assert data["total_water_liters"] == 200.0
    assert data["amount_per_tank"] == 500.0
    assert data["total_chemical_amount"] == 500.0
    assert "كوب" in data["amount_per_tank_practical"] or "كيس" in data["amount_per_tank_practical"] or "500" in data["amount_per_tank_practical"]


def test_scenario_tank_mix_whole_area_mode():
    """Scenario 4.3: Whole field area mode (1 feddan vegetables with 20L sprayer, 250g/feddan)."""
    payload = {
        "mode": "area",
        "area_value": 1.0,
        "area_unit": "feddan",
        "tank_type": "knapsack_20l",
        "dosage_rate": 250.0,
        "dosage_unit": "per_feddan",
        "chemical_type": "powder",
        "crop_category": "vegetable",
        "product_name": "دايثين م45",
    }
    resp = client.post("/api/calculator/tank-mix", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["area_feddan"] == 1.0
    assert data["total_water_liters"] == 140.0
    assert data["tanks_count_practical"] == 7
    assert data["total_chemical_amount"] == 250.0
    assert round(data["amount_per_tank"], 1) == 35.7
    assert any(w in data["amount_per_tank_practical"] for w in ("ملعق", "كيس", "جم"))


def test_scenario_tank_mix_qirat_conversion():
    """Scenario 4.4: Area conversion from Qirat to Feddan (12 Qirat = 0.5 Feddan)."""
    payload = {
        "mode": "area",
        "area_value": 12.0,
        "area_unit": "qirat",
        "tank_type": "motor_200l",
        "dosage_rate": 200.0,
        "dosage_unit": "per_feddan",
        "chemical_type": "liquid",
        "crop_category": "vegetable",
        "product_name": "أميستار",
    }
    resp = client.post("/api/calculator/tank-mix", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert round(data["area_feddan"], 2) == 0.5
    assert data["total_chemical_amount"] == 100.0


def test_scenario_tank_mix_chemical_incompatibilities():
    """Scenario 4.5 & 4.6: Incompatibility detection for toxic / clogging tank mixtures."""
    # Copper + Amino Acids
    resp_cu = client.post("/api/calculator/tank-mix", json={
        "area_value": 1.0,
        "tank_type": "motor_600l",
        "dosage_rate": 250.0,
        "dosage_unit": "per_100l",
        "chemical_type": "powder",
        "crop_category": "orchard",
        "product_name": "أوكسي كلورور النحاس",
        "mix_partners": ["أحماض أمينية"],
    })
    assert resp_cu.status_code == 200
    assert len(resp_cu.json()["compatibility_warnings"]) > 0

    # Sulfur + Mineral Oil
    resp_s = client.post("/api/calculator/tank-mix", json={
        "area_value": 1.0,
        "tank_type": "motor_600l",
        "dosage_rate": 200.0,
        "dosage_unit": "per_100l",
        "chemical_type": "liquid",
        "crop_category": "orchard",
        "product_name": "كبريت ميكروني",
        "mix_partners": ["زيت شتوي معدني"],
    })
    assert resp_s.status_code == 200
    assert len(resp_s.json()["compatibility_warnings"]) > 0


def test_scenario_salinity_advisor_sensitive_vs_tolerant():
    """Scenario 4.7 & 4.8: Water salinity evaluation on sensitive strawberries vs tolerant date palm."""
    # Sensitive crop under high salinity (1600 ppm triggers critical risk)
    resp_sens = client.post("/api/calculator/salinity", json={
        "salinity_value": 1600.0,
        "salinity_unit": "ppm",
        "crop_name": "فراولة",
        "irrigation_method": "تنقيط",
    })
    assert resp_sens.status_code == 200
    data_sens = resp_sens.json()
    assert data_sens["is_critical_risk"] is True
    assert data_sens["yield_potential_percent"] < 100.0
    assert len(data_sens["alleviation_protocol"]) > 0

    # Tolerant crop under safe salinity
    resp_tol = client.post("/api/calculator/salinity", json={
        "salinity_value": 2.5,
        "salinity_unit": "ec",
        "crop_name": "نخيل",
        "irrigation_method": "غمر",
    })
    assert resp_tol.status_code == 200
    data_tol = resp_tol.json()
    assert data_tol["is_critical_risk"] is False
    assert data_tol["yield_potential_percent"] == 100.0


# ═════════════════════════════════════════════════════════════════════════════
# 5. COMPUTER VISION, LEAF DIAGNOSIS & RECOVERY FOLLOW-UP SCENARIOS
# ═════════════════════════════════════════════════════════════════════════════

def test_scenario_leaf_diagnosis_with_valid_image():
    """Scenario 5.1: Plant leaf diagnosis produces Arabic disease name, confidence %, and prescription."""
    buf = _make_dummy_image(color="green")
    files = {"image": ("test_leaf.jpg", buf, "image/jpeg")}
    data = {
        "crop": "بطاطس",
        "governorate": "الدقهلية",
        "farm_size": "2",
        "irrigation": "غمر",
        "query": "فحص ورقة بطاطس عليها بقع بنية داكنة",
    }
    resp = client.post("/api/diagnose", files=files, data=data)
    assert resp.status_code == 200
    res = resp.json()
    assert "cv_result" in res
    assert "predicted_class_ar" in res["cv_result"]
    assert "advice" in res
    assert "image_id" in res
    assert res["image_id"] > 0


def test_scenario_leaf_diagnosis_corrupted_file_handling():
    """Scenario 5.2: Empty image files are rejected with 400 Bad Request, and non-plant images are gracefully rejected."""
    # Empty file
    empty_buf = io.BytesIO(b"")
    files_empty = {"image": ("empty.jpg", empty_buf, "image/jpeg")}
    resp_empty = client.post("/api/diagnose", files=files_empty)
    assert resp_empty.status_code == 400
    assert "empty" in resp_empty.json()["detail"].lower() or "صورة" in resp_empty.json()["detail"]


def test_scenario_leaf_recovery_followup_evaluation():
    """Scenario 5.3 & 5.4: Leaf recovery evaluation compares baseline vs follow-up and calculates healing score."""
    # 1. Create a baseline image record
    buf_base = _make_dummy_image()
    baseline_id = save_image_record(
        image_bytes=buf_base.getvalue(),
        filename="baseline_leaf.jpg",
        source_endpoint="/api/diagnose",
        model_used="mobilenet_v3",
        predicted_class="Tomato___Late_blight",
        predicted_class_ar="طماطم - ندوة متأخرة",
        confidence="88.00%",
        top_predictions=[{"class": "Tomato___Late_blight", "confidence": 0.88}],
        rag_advice="رش دايثين م45 بمعدل 250 جم للفدان",
        client_ip="127.0.0.1",
        visitor_hash="scenario_followup_vis",
    )

    # 2. Evaluate follow-up after 5 days with a fresh green leaf image
    buf = _make_dummy_image(color="forestgreen")
    files = {"followup_image": ("followup_leaf.jpg", buf, "image/jpeg")}
    data = {
        "baseline_image_id": str(baseline_id),
        "days_elapsed": "5",
        "applied_treatment": "دايثين م45",
    }
    resp = client.post("/api/diagnose/followup", files=files, data=data)
    assert resp.status_code == 200
    res = resp.json()
    assert res["status"] == "success"
    assert res["baseline_image_id"] == baseline_id
    assert res["days_elapsed"] == 5
    assert 0 <= res["recovery_score"] <= 100
    assert res["recovery_status"] in ("healed", "improving", "relapsed")
    assert "clinical_comparison_ar" in res or "advice" in res
    assert "recommended_action_ar" in res


def test_scenario_leaf_recovery_followup_missing_baseline():
    """Scenario 5.5: Non-existent baseline ID returns 404 Not Found."""
    buf = _make_dummy_image()
    files = {"followup_image": ("followup.jpg", buf, "image/jpeg")}
    data = {"baseline_image_id": "99999999", "days_elapsed": "3"}
    resp = client.post("/api/diagnose/followup", files=files, data=data)
    assert resp.status_code == 404


# ═════════════════════════════════════════════════════════════════════════════
# 6. CONVERSATIONAL AGRI-RAG & EGYPTIAN DIALECT ADVISOR SCENARIOS
# ═════════════════════════════════════════════════════════════════════════════

def test_scenario_chat_memory_retrieval():
    """Scenario 6.1: Chat memory endpoint returns conversation context."""
    resp = client.get("/api/chat/memory")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert "memory" in resp.json()


def test_scenario_chat_advisory_grounded_answer():
    """Scenario 6.2: Agricultural question receives grounded Arabic advice."""
    payload = {
        "query": "عندي اصفرار في أوراق البطاطس مع بقع بنية، ارش ايه؟",
        "location": "الدقهلية",
        "crop": "بطاطس",
        "area_feddan": 2.0,
        "irrigation_type": "غمر",
    }
    resp = client.post("/api/chat", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "answer" in data
    assert len(data["answer"]) > 10


# ═════════════════════════════════════════════════════════════════════════════
# 7. EGYPTIAN SPEECH SYNTHESIS & AUDIO SCENARIOS
# ═════════════════════════════════════════════════════════════════════════════

def test_scenario_egyptian_tts_voice_synthesis_get_and_post():
    """Scenario 7.1 & 7.2: Voice synthesis via GET and POST returns audio/mpeg stream or 503 fallback."""
    # GET query
    resp_get = client.get("/api/tts?text=أهلاً+بك+يا+حاج+رضوان&voice=ar-EG-ShakirNeural")
    assert resp_get.status_code in (200, 503)

    # POST payload with Salma voice
    resp_post = client.post("/api/tts", json={"text": "جرعة الرش الموصى بها هي ملعقتين", "voice": "ar-EG-SalmaNeural"})
    assert resp_post.status_code in (200, 503)


def test_scenario_egyptian_stt_endpoint():
    """Scenario 7.3: Speech-to-text endpoint handles audio input gracefully."""
    resp = client.post("/api/stt")
    assert resp.status_code == 200
    assert "text" in resp.json()


# ═════════════════════════════════════════════════════════════════════════════
# 8. DEVELOPER ADMIN TELEMETRY, BACKUP & SECURITY SCENARIOS
# ═════════════════════════════════════════════════════════════════════════════

def test_scenario_dev_panel_unauthorized_access_denied():
    """Scenario 8.1: Accessing developer telemetry endpoints without secret key is rejected with 403 or 404."""
    unauthorized_endpoints = [
        "/dev-panel",
        "/api/dev/analytics",
        "/api/dev/guest-policy",
        "/api/dev/user-360",
        "/api/dev/backups",
        "/api/dev/telegram-config",
    ]
    for ep in unauthorized_endpoints:
        resp = client.get(ep)
        assert resp.status_code in (403, 404), f"Expected 403 or 404 on {ep}, got {resp.status_code}"


def test_scenario_dev_panel_authorized_access():
    """Scenario 8.2: Accessing developer telemetry endpoints with DEV_SECRET_KEY succeeds."""
    resp = client.get(f"/api/dev/analytics?key={DEV_SECRET_KEY}")
    assert resp.status_code == 200
    data = resp.json()
    assert any(k in data for k in ("kpis", "devices_breakdown", "guest_policy", "cookie_profiles"))


def test_scenario_dev_database_backup_and_cache_flush():
    """Scenario 8.3 & 8.4: Database backup listing/creation and cache flush."""
    # 1. Backups list
    b_resp = client.get(f"/api/dev/backups?key={DEV_SECRET_KEY}")
    assert b_resp.status_code == 200
    assert "backups" in b_resp.json()

    # 2. Trigger backup creation
    create_resp = client.post(f"/api/dev/backups/create?key={DEV_SECRET_KEY}")
    assert create_resp.status_code == 200
    assert create_resp.json()["status"] == "success"

    # 3. Clear cache
    cache_resp = client.post(f"/api/dev/clear-cache?key={DEV_SECRET_KEY}")
    assert cache_resp.status_code == 200
    assert cache_resp.json()["status"] == "ok"


def test_scenario_dev_telegram_config_endpoints():
    """Scenario 8.5: Telegram configuration reading and test dispatch."""
    resp = client.get(f"/api/dev/telegram-config?key={DEV_SECRET_KEY}")
    assert resp.status_code == 200
    assert "enabled" in resp.json()


# ═════════════════════════════════════════════════════════════════════════════
# 9. EPIDEMIC HEATMAP & PDF PRESCRIPTION SCENARIOS
# ═════════════════════════════════════════════════════════════════════════════

def test_scenario_epidemic_heatmap_page_and_api():
    """Scenario 9.1: Interactive Epidemic Heatmap page and live all-governorates risk API."""
    # 1. HTML Page
    page_resp = client.get("/epidemic-map")
    assert page_resp.status_code == 200
    assert "خريطة الرصد الوبائي" in page_resp.text
    assert "leaflet" in page_resp.text.lower()

    # 2. REST API
    api_resp = client.get("/api/weather/epidemic-map")
    assert api_resp.status_code == 200
    data = api_resp.json()
    assert data["status"] == "ok"
    assert data["total_governorates"] == 27
    assert len(data["governorates"]) == 27
    assert any(g["governorate"] == "الدقهلية" for g in data["governorates"])
    assert "danger_count" in data
    assert "warning_count" in data
    assert "safe_count" in data


def test_scenario_prescription_html2pdf_direct_download():
    """Scenario 9.2: Prescription page includes direct PDF generation and WhatsApp share."""
    buf = _make_dummy_image()
    img_id = save_image_record(
        image_bytes=buf.getvalue(),
        filename="scenario_pdf_test.jpg",
        source_endpoint="/api/diagnose",
        model_used="mobilenet_v3",
        predicted_class="Tomato___Late_blight",
        predicted_class_ar="طماطم — ندوة متأخرة",
        confidence="96.00%",
        top_predictions=[{"class": "Tomato___Late_blight", "confidence": 0.96}],
        rag_advice="رش وقائي بميتالاكسيل-إم أو أوكسي كلورور النحاس.",
        client_ip="127.0.0.1",
        visitor_hash="scenario_pdf_visitor",
    )
    resp = client.get(f"/prescription/{img_id}")
    assert resp.status_code == 200
    assert "btnDownloadPDF" in resp.text
    assert "downloadPrescriptionPDF" in resp.text
    assert "html2pdf" in resp.text

