"""Comprehensive Logic & Physical Subsystem Audit.

Verifies that EVERY subsystem function works correctly in:
1. Logic: Agronomic math, conversions, algorithms, constraints, intent classification, security isolation.
2. Physical: File I/O, SQLite schema & rows, model inference, memory structures, HTTP status codes, audio streams.
"""

from __future__ import annotations

import asyncio
import io
import logging
import math
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Ensure project root & agri-rag are on sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(ROOT_DIR / "agri-rag") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "agri-rag"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("system_audit")


class AuditResult:
    def __init__(self, subsystem: str, function_name: str, check_type: str, passed: bool, details: str):
        self.subsystem = subsystem
        self.function_name = function_name
        self.check_type = check_type  # "Logic" or "Physical"
        self.passed = passed
        self.details = details


results: List[AuditResult] = []


def record(subsystem: str, function_name: str, check_type: str, passed: bool, details: str) -> None:
    results.append(AuditResult(subsystem, function_name, check_type, passed, details))


# ─── 1. Agronomic Calculators Subsystem ────────────────────────────────────────

def audit_calculators():
    from app.schemas.calculator import SalinityRequest, TankMixRequest
    from app.services.agri_calculator_service import calculate_tank_mix, evaluate_water_salinity

    # 1.1 Direct Tank Filling Mode (Logic & Math)
    req_tank = TankMixRequest(
        mode="tank",
        tanks_count=1,
        tank_type="knapsack_20l",
        dosage_rate=50.0,
        dosage_unit="per_100l",
        chemical_type="liquid",
        crop_category="vegetable",
        product_name="مبيد حشري سائل",
    )
    res_tank = calculate_tank_mix(req_tank)
    # 20L tank at 50ml per 100L -> 10ml
    ok_tank = math.isclose(res_tank.amount_per_tank, 10.0, rel_tol=1e-3) and res_tank.total_water_liters == 20.0
    record("Calculators", "calculate_tank_mix(mode=tank)", "Logic", ok_tank, f"Expected 10ml in 20L, got {res_tank.amount_per_tank}ml")

    # 1.2 Whole Area Mode + Qirat Conversion (12 qirats = 0.5 feddan)
    req_qirat = TankMixRequest(
        mode="area",
        area_value=12.0,
        area_unit="qirat",
        tank_type="motor_200l",
        dosage_rate=200.0,
        dosage_unit="per_feddan",
        chemical_type="liquid",
        crop_category="vegetable",
        product_name="أميستار",
    )
    res_qirat = calculate_tank_mix(req_qirat)
    # 0.5 feddan * 200 ml/feddan = 100 ml total chemical
    ok_qirat = math.isclose(res_qirat.area_feddan, 0.5, rel_tol=1e-3) and math.isclose(res_qirat.total_chemical_amount, 100.0, rel_tol=1e-3)
    record("Calculators", "calculate_tank_mix(qirat_conversion)", "Logic", ok_qirat, f"Feddan={res_qirat.area_feddan}, TotalChem={res_qirat.total_chemical_amount}ml")

    # 1.3 Chemical Incompatibility Detection (Safety)
    req_incompat = TankMixRequest(
        area_value=1.0,
        tank_type="motor_600l",
        dosage_rate=250.0,
        dosage_unit="per_100l",
        chemical_type="powder",
        crop_category="orchard",
        product_name="أوكسي كلورور النحاس",
        mix_partners=["أحماض أمينية"],
    )
    res_incompat = calculate_tank_mix(req_incompat)
    has_warning = len(res_incompat.compatibility_warnings) > 0 and any("النحاس" in w for w in res_incompat.compatibility_warnings)
    record("Calculators", "chemical_incompatibility_check", "Logic", has_warning, f"Warnings count={len(res_incompat.compatibility_warnings)}, text contains النحاس={has_warning}")

    # 1.4 Salinity Evaluation (Crop Risk Thresholds)
    # Sensitive crop: Strawberry at 1600 ppm (EC 2.5) -> Critical Risk
    req_sens = SalinityRequest(
        salinity_value=1600.0,
        salinity_unit="ppm",
        crop_name="فراولة",
        irrigation_method="تنقيط",
    )
    res_sens = evaluate_water_salinity(req_sens)
    ok_sens = res_sens.is_critical_risk is True and res_sens.yield_potential_percent < 100.0 and len(res_sens.alleviation_protocol) > 0
    record("Calculators", "evaluate_water_salinity(strawberry_sensitive)", "Logic", ok_sens, f"CriticalRisk={res_sens.is_critical_risk}, YieldPotential={res_sens.yield_potential_percent}%")

    # Tolerant crop: Palm at 2.5 dS/m -> Low / Safe
    req_tol = SalinityRequest(
        salinity_value=2.5,
        salinity_unit="ec",
        crop_name="نخيل",
        irrigation_method="غمر",
    )
    res_tol = evaluate_water_salinity(req_tol)
    ok_tol = res_tol.is_critical_risk is False and res_tol.yield_potential_percent == 100.0
    record("Calculators", "evaluate_water_salinity(palm_tolerant)", "Logic", ok_tol, f"CriticalRisk={res_tol.is_critical_risk}, YieldPotential={res_tol.yield_potential_percent}%")


# ─── 2. Computer Vision & Specialists Subsystem ───────────────────────────────

def audit_computer_vision():
    from PIL import Image
    from computer_vision.inference.classifier import PlantDiseaseClassifier
    from computer_vision.inference.crop_specialists import (
        diagnose_expanded_crop,
        filter_predictions_by_crop,
        is_expanded_crop,
        normalize_crop_hint,
    )

    # 2.1 Physical Model Weights Check
    model_path = ROOT_DIR / "computer_vision" / "models" / "EfficientNetV2B2_best.keras"
    file_exists = model_path.exists()
    file_size_mb = model_path.stat().st_size / (1024 * 1024) if file_exists else 0
    record("ComputerVision", "model_weights_file", "Physical", file_exists and file_size_mb > 30, f"Exists={file_exists}, Size={file_size_mb:.2f} MB")

    # 2.2 Visual Gatekeeper: validate_plant_image_opencv
    classifier = PlantDiseaseClassifier()

    # White image: no green plant tissue
    white_img = Image.new("RGB", (256, 256), (255, 255, 255))
    buf_w = io.BytesIO()
    white_img.save(buf_w, format="JPEG")
    res_white = classifier.validate_plant_image_opencv(buf_w.getvalue())
    ok_white = res_white.get("green_foliage_pct", 0) < 18.0 and not res_white.get("is_plant")
    record("ComputerVision", "validate_plant_image_opencv(white_image)", "Logic", ok_white, f"is_plant={res_white.get('is_plant')}, foliage_pct={res_white.get('green_foliage_pct')}%")

    # Green synthetic leaf image
    green_img = Image.new("RGB", (256, 256), (40, 160, 40))
    buf_g = io.BytesIO()
    green_img.save(buf_g, format="JPEG")
    res_green = classifier.validate_plant_image_opencv(buf_g.getvalue())
    ok_green = res_green.get("is_plant") and res_green.get("green_foliage_pct", 0) >= 50.0
    record("ComputerVision", "validate_plant_image_opencv(green_leaf)", "Logic", ok_green, f"is_plant={res_green.get('is_plant')}, foliage_pct={res_green.get('green_foliage_pct')}%")

    # 2.3 Physical Inference Execution
    pred_res = classifier.predict(buf_g.getvalue(), top_k=3)
    has_preds = len(pred_res.get("top_predictions", [])) > 0
    conf_sum = sum(float(str(p["confidence"]).replace("%", "")) for p in pred_res.get("top_predictions", []))
    ok_pred = has_preds and (0.0 <= conf_sum <= 105.0)
    record("ComputerVision", "classifier.predict(physical_inference)", "Physical", ok_pred, f"Top predictions count={len(pred_res.get('top_predictions', []))}")

    # 2.4 Crop Specialists (Mango & Wheat expanded catalogues)
    norm_crop = normalize_crop_hint("مانجا زبدية")
    ok_norm = norm_crop == "مانجو"
    record("ComputerVision", "normalize_crop_hint", "Logic", ok_norm, f"Expected مانجو, got {norm_crop}")

    is_exp = is_expanded_crop(norm_crop)
    record("ComputerVision", "is_expanded_crop(مانجو)", "Logic", is_exp, f"Expected True, got {is_exp}")

    # Diagnose expanded mango
    diag_mango = diagnose_expanded_crop(norm_crop, res_green)
    has_mango_label = bool(diag_mango and diag_mango.get("predicted_class"))
    record("ComputerVision", "diagnose_expanded_crop(مانجو)", "Logic", has_mango_label, f"Class={diag_mango.get('predicted_class')}, conf={diag_mango.get('confidence')}")

    # 2.5 Crop Filter Probability Renormalization
    raw_preds = [
        {"class": "Tomato___Late_blight", "confidence": 0.60},
        {"class": "Potato___Late_blight", "confidence": 0.30},
        {"class": "Apple___Black_rot", "confidence": 0.10},
    ]
    top_3, normalized_detailed = filter_predictions_by_crop(raw_preds, "طماطم")
    filtered_classes = [p["class"] for p in normalized_detailed]
    only_tomato = all("Tomato" in c for c in filtered_classes)
    renorm_conf = normalized_detailed[0]["confidence"] if normalized_detailed else 0.0
    ok_filter = only_tomato and math.isclose(renorm_conf, 1.0, rel_tol=1e-3)
    record("ComputerVision", "filter_predictions_by_crop(renormalization)", "Logic", ok_filter, f"Only tomato={only_tomato}, renorm_conf={renorm_conf}")


# ─── 3. Database & Storage Subsystem ──────────────────────────────────────────

def audit_database() -> Tuple[Dict[str, Any], str]:
    from computer_vision.storage.chat_repository import get_agent_memory_context, save_chat_log
    from computer_vision.storage.connection import DB_PATH, get_db_connection, init_db
    from computer_vision.storage.image_repository import get_image_record_by_id, save_image_record
    from computer_vision.storage.user_repository import authenticate_user, register_user
    from computer_vision.storage.utils import create_auth_token, verify_auth_token, verify_password

    # 3.1 Physical DB File & Tables
    init_db()
    db_exists = Path(DB_PATH).exists()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}

    required_tables = {"users", "chat_logs", "uploaded_images", "visitor_logs", "error_logs"}
    has_all_tables = required_tables.issubset(tables)
    record("Storage", "init_db(schema_and_tables)", "Physical", db_exists and has_all_tables, f"DB Exists={db_exists}, Found tables: {sorted(tables)}")

    # 3.2 User Auth: Password Hashing (PBKDF2-HMAC-SHA256) & Token Roundtrip
    unique_user = f"audit_{int(time.time())}@gmail.com"
    user_data, err = register_user(
        full_name="مهندس أحمد",
        identifier_raw=unique_user,
        password="ValidPassword123!",
        governorate="الشرقية",
        primary_crop="قمح",
        farm_size_feddan=10.0,
        irrigation_type="تنقيط",
    )
    ok_reg = user_data is not None and not err
    record("Storage", "register_user", "Logic", ok_reg, f"User ID={user_data.get('id') if user_data else None}, Error={err}")

    # Verify Password Hash is PBKDF2-HMAC-SHA256
    if user_data:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT password_hash FROM users WHERE id = ?", (user_data["id"],))
            pw_hash = c.fetchone()[0]
        is_pbkdf2 = pw_hash.startswith("pbkdf2_sha256$")
        pw_verified = verify_password("ValidPassword123!", pw_hash)
        record("Storage", "password_pbkdf2_hashing", "Security", is_pbkdf2 and pw_verified, f"PBKDF2={is_pbkdf2}, Verify={pw_verified}")

    # Login and token verification
    logged_user, log_err = authenticate_user(unique_user, "ValidPassword123!")
    ok_login = logged_user is not None and not log_err
    token = create_auth_token(logged_user) if logged_user else ""
    verified = verify_auth_token(token) if token else None
    token_valid = verified is not None and str(verified.get("uid")) == str(logged_user["id"])
    record("Storage", "login_and_jwt_token_roundtrip", "Security", ok_login and token_valid, f"Logged ID={logged_user.get('id') if logged_user else None}, Token valid={token_valid}")

    # 3.3 Image Record Storage & Retrieval
    img_id = save_image_record(
        image_bytes=b"dummy_bytes_12345",
        filename="audit_leaf.jpg",
        source_endpoint="/api/diagnose",
        model_used="EfficientNetV2B2",
        predicted_class="Tomato___Late_blight",
        confidence="92.50%",
        top_predictions=[{"class": "Tomato___Late_blight", "confidence": 0.925}],
        predicted_class_ar="طماطم - ندوة متأخرة",
        user_id=user_data.get("id") if user_data else None,
    )
    saved_rec = get_image_record_by_id(img_id)
    ok_rec = saved_rec is not None and saved_rec.get("predicted_class") == "Tomato___Late_blight"
    record("Storage", "save_and_get_image_record", "Physical", ok_rec, f"Saved ID={img_id}, Retrieved class={saved_rec.get('predicted_class') if saved_rec else None}")

    # 3.4 Chat History & Account Strict Isolation
    session_id_a = f"sess_a_{int(time.time())}"
    user_id_a = user_data["id"] if user_data else 99999
    save_chat_log(
        user_query="عندي مشكلة في القمح",
        bot_answer="رش سلفات بوتاسيوم",
        session_id=session_id_a,
        crop="قمح",
        user_id=user_id_a,
    )

    # User A requests memory: should retrieve 1 turn
    mem_a = get_agent_memory_context(session_id=session_id_a, user_id=user_id_a)
    has_turn_a = len(mem_a.get("turns", [])) >= 1
    record("Storage", "save_and_retrieve_chat_memory", "Physical", has_turn_a, f"Turns retrieved for User A: {len(mem_a.get('turns', []))}")

    # User B requests User A's session: should retrieve 0 turns (strict account isolation)
    user_id_b = user_id_a + 999
    mem_b = get_agent_memory_context(session_id=session_id_a, user_id=user_id_b)
    has_no_leak = len(mem_b.get("turns", [])) == 0
    record("Storage", "account_isolation_chat_memory", "Security", has_no_leak, f"Turns leaked to User B: {len(mem_b.get('turns', []))}")

    return user_data or {}, token


# ─── 4. Arabic NLP & RAG Subsystem ────────────────────────────────────────────

def audit_rag():
    from agri_rag.nlp.arabic import classify_user_query
    from rag.preprocess import canonicalize_terms, normalize_arabic_text

    # 4.1 Orthographic Normalization
    raw_ar = "أَحْمَدُ إِبْرَاهِيم آتَى بِالْمُبِيدَاتِ سلااااام"
    norm = normalize_arabic_text(raw_ar)
    expected_norm = "احمد ابراهيم اتي بالمبيدات سلاام"
    ok_norm = norm == expected_norm
    record("ArabicNLP", "normalize_arabic_text", "Logic", ok_norm, f"Expected '{expected_norm}', got '{norm}'")

    # 4.2 Lexicon Canonicalization
    lexicon = {
        "dialect_aliases": {"لفحة متاخرة": ["ندوة", "الندوة"], "كبريت زراعي": ["عفار"]},
        "product_aliases": {"سماد مركبي NPK": ["npk", "الـ npk"]},
    }
    canon = canonicalize_terms("عندي ندوة في الطماطم وعايز عفار وnpk", lexicon)
    ok_canon = "لفحة متاخرة" in canon and "كبريت زراعي" in canon and "سماد مركبي NPK" in canon
    record("ArabicNLP", "canonicalize_terms", "Logic", ok_canon, f"Canonicalized: '{canon}'")

    # 4.3 Intent Classification: All 6 Intents
    # Intent 1: Unintelligible (gibberish keyboard mash)
    q1 = classify_user_query("حهىل")
    ok_q1 = q1.intent == "unintelligible" and q1.suggested_fast_response is not None and not q1.requires_retrieval
    record("RAG", "intent_unintelligible(gibberish)", "Logic", ok_q1, f"Intent={q1.intent}, FastResponse={bool(q1.suggested_fast_response)}")

    # Intent 2: Unintelligible (symbols)
    q2 = classify_user_query("????!@#$")
    ok_q2 = q2.intent == "unintelligible"
    record("RAG", "intent_unintelligible(symbols)", "Logic", ok_q2, f"Intent={q2.intent}")

    # Intent 3: Needs clarification (vague query without prior context)
    q3 = classify_user_query("اعمل ايه؟", has_context=False)
    ok_q3 = q3.intent == "needs_clarification" and "تحت أمرك" in (q3.suggested_fast_response or "")
    record("RAG", "intent_needs_clarification(no_context)", "Logic", ok_q3, f"Intent={q3.intent}")

    # Intent 4: Follow-up clarification WITH context (proceeds to agricultural diagnosis)
    q4 = classify_user_query("اعمل ايه؟", has_context=True)
    ok_q4 = q4.intent == "standard_agricultural" and q4.requires_retrieval is True
    record("RAG", "intent_followup_with_context", "Logic", ok_q4, f"Intent={q4.intent}, requires_retrieval={q4.requires_retrieval}")

    # Intent 5: Quick direct ("كلمتين ويسكت")
    q5 = classify_user_query("ينفع اخلط نحاس مع سماد ورقي؟")
    ok_q5 = q5.intent == "quick_direct" and q5.suggested_max_tokens <= 250
    record("RAG", "intent_quick_direct", "Logic", ok_q5, f"Intent={q5.intent}, token_budget={q5.suggested_max_tokens}")

    # Intent 6: Comprehensive protocol
    q6 = classify_user_query("عايز برنامج تسميد كامل للبطاطس من الزراعة للحصاد")
    ok_q6 = q6.intent == "comprehensive_protocol" and q6.suggested_max_tokens >= 1000
    record("RAG", "intent_comprehensive_protocol", "Logic", ok_q6, f"Intent={q6.intent}, token_budget={q6.suggested_max_tokens}")

    # Intent 7: Chit-chat
    q7 = classify_user_query("صباح الخير يا باشمهندس")
    ok_q7 = q7.intent == "chit_chat" and not q7.requires_retrieval
    record("RAG", "intent_chit_chat", "Logic", ok_q7, f"Intent={q7.intent}, FastResponse={bool(q7.suggested_fast_response)}")


# ─── 5. Weather Subsystem ─────────────────────────────────────────────────────

def audit_weather():
    from app.services.weather_service import fetch_weather_forecast, nearest_governorate

    # 5.1 GPS Nearest Mapping
    resolved_gov = nearest_governorate(30.0444, 31.2357)
    ok_gps = resolved_gov in ("القاهرة", "الجيزة")
    record("Weather", "nearest_governorate(30.04, 31.23)", "Logic", ok_gps, f"Resolved Governorate={resolved_gov}")

    # 5.2 Physical Weather Fetch for Egyptian Agricultural Governorate
    w_data = asyncio.run(fetch_weather_forecast("الدقهلية"))
    ok_w = w_data is not None and w_data.temperature is not None
    record("Weather", "fetch_weather_forecast(الدقهلية)", "Physical", ok_w, f"Temp={w_data.temperature}C, Humidity={w_data.humidity}%, Alerts={len(w_data.alerts)}")


# ─── 6. Audio Synthesis & TTS Subsystem ────────────────────────────────────────

def audit_audio():
    from app.services.audio_service import synthesize_speech, to_spoken_egyptian_arabic

    # 6.1 Spoken Egyptian Normalization
    formal = "سوف نقوم برش المبيدات في الصباح الباكر"
    spoken = to_spoken_egyptian_arabic(formal)
    ok_spoken = bool(spoken and len(spoken) > 5)
    record("AudioTTS", "to_spoken_egyptian_arabic", "Logic", ok_spoken, f"Spoken: '{spoken}'")

    # 6.2 Physical Speech Synthesis
    audio_bytes, mime = asyncio.run(synthesize_speech("أهلاً بك في الخبير الزراعي", voice="ar-EG-SalmaNeural"))
    has_bytes = audio_bytes is not None and len(audio_bytes) > 200
    is_valid_audio = False
    if has_bytes:
        is_valid_audio = audio_bytes.startswith(b"ID3") or audio_bytes[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2") or audio_bytes.startswith(b"RIFF")
    record("AudioTTS", "synthesize_speech", "Physical", is_valid_audio, f"Bytes={len(audio_bytes) if audio_bytes else 0}, Mime={mime}")


# ─── 7. FastAPI End-to-End HTTP Physical Endpoints ────────────────────────────

def audit_http_endpoints(user_data: Dict[str, Any], auth_token: str):
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    auth_headers = {"Authorization": f"Bearer {auth_token}"} if auth_token else {}

    # 7.1 GET /health
    r_health = client.get("/health")
    ok_health = r_health.status_code == 200 and r_health.json().get("status") == "healthy"
    record("HTTP", "GET /health", "Physical", ok_health, f"Status={r_health.status_code}, Services={list(r_health.json().get('services', {}).keys())}")

    # 7.2 POST /api/calculator/tank-mix
    payload_mix = {
        "mode": "area",
        "area_value": 1.0,
        "area_unit": "feddan",
        "tank_type": "knapsack_20l",
        "dosage_rate": 250.0,
        "dosage_unit": "per_feddan",
        "chemical_type": "powder",
        "crop_category": "vegetable",
        "product_name": "ريدوميل جولد",
    }
    r_mix = client.post("/api/calculator/tank-mix", json=payload_mix)
    data_mix = r_mix.json()
    ok_mix = r_mix.status_code == 200 and data_mix.get("total_chemical_amount") == 250.0 and data_mix.get("tanks_count_practical") == 7
    record("HTTP", "POST /api/calculator/tank-mix", "Physical", ok_mix, f"Status={r_mix.status_code}, Tanks={data_mix.get('tanks_count_practical')}, TotalChem={data_mix.get('total_chemical_amount')}g")

    # 7.3 POST /api/calculator/salinity
    payload_sal = {
        "salinity_value": 1600.0,
        "salinity_unit": "ppm",
        "crop_name": "فراولة",
        "irrigation_method": "تنقيط",
    }
    r_sal = client.post("/api/calculator/salinity", json=payload_sal)
    data_sal = r_sal.json()
    ok_sal = r_sal.status_code == 200 and data_sal.get("is_critical_risk") is True
    record("HTTP", "POST /api/calculator/salinity", "Physical", ok_sal, f"Status={r_sal.status_code}, CriticalRisk={data_sal.get('is_critical_risk')}, Yield={data_sal.get('yield_potential_percent')}%")

    # 7.4 POST /api/chat (Authenticated Request - Fast Path)
    r_chat_gib = client.post("/api/chat", json={"query": "حهىل"}, headers=auth_headers)
    data_chat_gib = r_chat_gib.json()
    ok_chat_gib = r_chat_gib.status_code == 200 and len(data_chat_gib.get("answer", "")) > 10
    record("HTTP", "POST /api/chat(unintelligible)", "Physical", ok_chat_gib, f"Status={r_chat_gib.status_code}, AnswerLen={len(data_chat_gib.get('answer', ''))}")

    # 7.5 POST /api/diagnose (Synthetic Leaf Image with Authentication)
    from PIL import Image
    buf = io.BytesIO()
    leaf = Image.new("RGB", (256, 256), (30, 150, 30))
    leaf.save(buf, format="JPEG")
    buf.seek(0)

    files = {"image": ("test_leaf.jpg", buf, "image/jpeg")}
    r_diag = client.post("/api/diagnose", files=files, data={"crop": "طماطم"}, headers=auth_headers)
    data_diag = r_diag.json()
    ok_diag = r_diag.status_code == 200 and "cv_result" in data_diag
    record("HTTP", "POST /api/diagnose", "Physical", ok_diag, f"Status={r_diag.status_code}, PredictedAr={data_diag.get('cv_result', {}).get('predicted_class_ar')}")


def run_full_audit():
    print("\n" + "=" * 80)
    print("🌾 SMART AGRICULTURE AI — FULL LOGIC & PHYSICAL SUBSYSTEM AUDIT")
    print("=" * 80 + "\n")

    user_data: Dict[str, Any] = {}
    auth_token: str = ""

    # 1. Calculators
    try:
        audit_calculators()
        print("✅ Agronomic Calculators: Audit complete")
    except Exception as e:
        logger.error(f"❌ Agronomic Calculators failed: {e}", exc_info=True)
        record("Calculators", "runner_exception", "Execution", False, str(e))

    # 2. Computer Vision
    try:
        audit_computer_vision()
        print("✅ Computer Vision & Specialists: Audit complete")
    except Exception as e:
        logger.error(f"❌ Computer Vision & Specialists failed: {e}", exc_info=True)
        record("ComputerVision", "runner_exception", "Execution", False, str(e))

    # 3. Database & Storage
    try:
        user_data, auth_token = audit_database()
        print("✅ Database & Persistence: Audit complete")
    except Exception as e:
        logger.error(f"❌ Database & Persistence failed: {e}", exc_info=True)
        record("Storage", "runner_exception", "Execution", False, str(e))

    # 4. Arabic NLP & RAG
    try:
        audit_rag()
        print("✅ Arabic NLP & RAG: Audit complete")
    except Exception as e:
        logger.error(f"❌ Arabic NLP & RAG failed: {e}", exc_info=True)
        record("RAG", "runner_exception", "Execution", False, str(e))

    # 5. Weather
    try:
        audit_weather()
        print("✅ Weather Subsystem: Audit complete")
    except Exception as e:
        logger.error(f"❌ Weather Subsystem failed: {e}", exc_info=True)
        record("Weather", "runner_exception", "Execution", False, str(e))

    # 6. Audio TTS
    try:
        audit_audio()
        print("✅ Audio & Speech TTS: Audit complete")
    except Exception as e:
        logger.error(f"❌ Audio & Speech TTS failed: {e}", exc_info=True)
        record("AudioTTS", "runner_exception", "Execution", False, str(e))

    # 7. HTTP API Physical Endpoints
    try:
        audit_http_endpoints(user_data, auth_token)
        print("✅ HTTP API Physical Endpoints: Audit complete")
    except Exception as e:
        logger.error(f"❌ HTTP API Physical Endpoints failed: {e}", exc_info=True)
        record("HTTP", "runner_exception", "Execution", False, str(e))

    print("\n" + "=" * 80)
    print("📊 DETAILED AUDIT VERIFICATION TABLE")
    print("=" * 80)

    total_checks = len(results)
    passed_checks = sum(1 for r in results if r.passed)
    failed_checks = total_checks - passed_checks

    for r in results:
        status_icon = "🟢 PASSED" if r.passed else "🔴 FAILED"
        print(f"[{status_icon}] [{r.subsystem:<14}] [{r.check_type:<8}] {r.function_name:<42} -> {r.details}")

    print("\n" + "=" * 80)
    print(f"SUMMARY: {passed_checks}/{total_checks} Checks Passed ({passed_checks / max(1, total_checks) * 100:.1f}%)")
    print("=" * 80 + "\n")

    if failed_checks > 0:
        sys.exit(1)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    run_full_audit()
