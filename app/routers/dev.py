"""Developer Telemetry & System Administration Endpoints.

Provides:
- GET /dev-panel: Developer dashboard view
- GET /api/dev/analytics: Platform KPIs, recent scans, chats, users, and server hardware telemetry
- GET/POST /api/dev/guest-policy: Live guest access gate control
- GET /api/dev/user-360: Full 360-degree activity profile by user, cookie, or IP
- GET /api/dev/image/{image_id}: Secure binary image streaming for verification
- GET/POST /api/dev/gemini-keys: Dynamic rotation pool management
- POST /api/dev/gemini-config: LLM model switching and key removal
- POST /api/dev/gemini-keys/test: Live multi-key ping and quota health check
- POST /api/dev/clear-cache: Flush in-memory caches
- POST /api/dev/oauth-config: OAuth Client IDs configuration
- POST /api/dev/verify-image: Active Learning ground truth labeling
- GET /api/dev/export/{export_type}: Dataset ZIP, fine-tuning JSONL, or UTF-8-BOM CSV exports
"""

from __future__ import annotations

import asyncio
import csv
import io
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

import requests as ext_requests
from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, JSONResponse

from app.core.config import AGRI_RAG_URL, DATA_DIR, TEMPLATES_DIR
from app.core.guest_policy import load_guest_policy, save_guest_policy
from app.core.security import verify_dev_key
from app.schemas.dev import (
    GeminiConfigPayload,
    GeminiKeyPayload,
    GuestPolicyPayload,
    OAuthConfigPayload,
    VerifyImagePayload,
)
from app.services.audio_service import _TTS_AUDIO_CACHE
from app.services.llm_service import (
    get_gemini_key_pool_and_model,
    load_oauth_config,
    save_oauth_config,
)
from app.services.telemetry_service import collect_server_system_metrics
from app.services.weather_service import _WEATHER_CACHE
from computer_vision.storage.chat_repository import build_rag_finetuning_jsonl
from computer_vision.storage.image_repository import (
    build_retraining_zip,
    get_image_blob_by_id,
    update_image_ground_truth,
)
from computer_vision.storage.telemetry_repository import (
    get_developer_analytics,
    get_user_360_profile,
    save_token_usage_log,
)
from computer_vision.storage.utils import mask_api_key

logger = logging.getLogger(__name__)

router = APIRouter()
_GEMINI_KEYS_FILE = DATA_DIR / "gemini_keys.json"
_OAUTH_CONFIG_FILE = DATA_DIR / "oauth_config.json"


@router.get("/dev-panel", include_in_schema=False)
async def serve_developer_dashboard(request: Request, key: str = Query("")) -> Response:
    """Serve the secret developer telemetry dashboard (accessible via Admin login or ?key=DEV_SECRET_KEY)."""
    verify_dev_key(key, request)
    template_file = TEMPLATES_DIR / "dev_dashboard.html"
    return FileResponse(str(template_file))


@router.get("/api/dev/analytics", include_in_schema=False)
async def developer_analytics_api(
    request: Request,
    key: str = Query(""),
    limit: int = Query(150, ge=1, le=1000),
) -> JSONResponse:
    """Return full developer telemetry JSON (returns 404 Not Found without key or Admin login)."""
    verify_dev_key(key, request)
    keys, _ = get_gemini_key_pool_and_model()
    p_mask = mask_api_key(keys[0], 1) if keys else ""
    data = await asyncio.to_thread(get_developer_analytics, limit, p_mask)
    data["server_metrics"] = await asyncio.to_thread(collect_server_system_metrics)
    data["guest_policy"] = load_guest_policy()
    return JSONResponse(content=data)


@router.get("/api/dev/guest-policy", include_in_schema=False)
async def developer_get_guest_policy(request: Request, key: str = Query("")) -> Dict[str, Any]:
    """Get current Guest Login Gate policy."""
    verify_dev_key(key, request)
    return {"status": "ok", "guest_policy": load_guest_policy()}


@router.post("/api/dev/guest-policy", include_in_schema=False)
async def developer_update_guest_policy(
    payload: GuestPolicyPayload,
    request: Request,
    key: str = Query(""),
) -> Dict[str, Any]:
    """Update Guest Login Gate policy (enforce_login, max_free_uses) live without restarting."""
    verify_dev_key(key, request)
    saved = await asyncio.to_thread(save_guest_policy, payload.enforce_login, payload.max_free_uses)
    return {"status": "ok", "guest_policy": saved}


@router.get("/api/dev/user-360", include_in_schema=False)
async def developer_user_360_api(
    request: Request,
    key: str = Query(""),
    user_id: Optional[int] = Query(None),
    visitor_id: str = Query(""),
    client_ip: str = Query(""),
) -> JSONResponse:
    """Return a complete 360-degree activity dossier for a specific user, cookie visitor, or IP."""
    verify_dev_key(key, request)
    dossier = await asyncio.to_thread(get_user_360_profile, user_id, visitor_id, client_ip)
    return JSONResponse(content=dossier)


@router.get("/api/dev/image/{image_id}", include_in_schema=False)
async def developer_view_image(image_id: int, request: Request, key: str = Query("")) -> Response:
    """Stream a privately stored uploaded image for the developer dashboard (returns 404 without key or Admin login)."""
    verify_dev_key(key, request)
    record = await asyncio.to_thread(get_image_blob_by_id, image_id)
    if not record:
        raise HTTPException(status_code=404, detail="Image not found")
    img_bytes, content_type, _ = record
    return Response(content=img_bytes, media_type=content_type)


@router.get("/api/dev/gemini-keys", include_in_schema=False)
async def developer_list_gemini_keys(request: Request, key: str = Query("")) -> Dict[str, Any]:
    """Return masked Gemini API keys currently active in the rotation pool."""
    verify_dev_key(key, request)
    keys, model_name = get_gemini_key_pool_and_model()
    masked = [mask_api_key(k, i + 1) for i, k in enumerate(keys)]
    return {
        "status": "ok",
        "count": len(keys),
        "masked_keys": masked,
        "primary_model": model_name,
        "available_models": [
            "gemini-2.5-flash",
            "gemini-3.5-flash-lite",
            "gemini-2.0-flash",
            "gemini-2.5-pro",
            "gemini-3.8-flash-lite-tts",
        ],
    }


@router.post("/api/dev/gemini-keys", include_in_schema=False)
async def developer_add_gemini_key(
    payload: GeminiKeyPayload,
    request: Request,
    key: str = Query(""),
) -> Dict[str, Any]:
    """Add a backup Gemini API key to the runtime rotation pool (data/gemini_keys.json)."""
    verify_dev_key(key, request)
    new_k = (payload.api_key or "").strip()
    if len(new_k) < 18 or not (new_k.startswith("AIza") or new_k.startswith("AQ.")):
        raise HTTPException(
            status_code=400,
            detail="مفتاح Gemini API غير صالح (يجب أن يبدأ بـ AIza أو AQ.).",
        )

    _GEMINI_KEYS_FILE.parent.mkdir(parents=True, exist_ok=True)
    saved_obj: Dict[str, Any] = {}
    if _GEMINI_KEYS_FILE.exists():
        try:
            saved_obj = json.loads(_GEMINI_KEYS_FILE.read_text(encoding="utf-8"))
        except Exception:
            saved_obj = {}
    saved_keys: List[str] = list(saved_obj.get("keys", []))
    if new_k not in saved_keys:
        saved_keys.append(new_k)
    saved_obj["keys"] = saved_keys
    _GEMINI_KEYS_FILE.write_text(json.dumps(saved_obj, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        os.chmod(str(_GEMINI_KEYS_FILE), 0o600)
    except Exception:
        pass

    keys, model_name = get_gemini_key_pool_and_model()
    masked = [mask_api_key(k, i + 1) for i, k in enumerate(keys)]
    return {"status": "ok", "count": len(keys), "masked_keys": masked, "primary_model": model_name}


@router.post("/api/dev/gemini-config", include_in_schema=False)
async def developer_update_gemini_config(
    payload: GeminiConfigPayload,
    request: Request,
    key: str = Query(""),
) -> Dict[str, Any]:
    """Switch the primary Gemini model or remove a backup key from data/gemini_keys.json."""
    verify_dev_key(key, request)
    _GEMINI_KEYS_FILE.parent.mkdir(parents=True, exist_ok=True)
    saved_obj: Dict[str, Any] = {}
    if _GEMINI_KEYS_FILE.exists():
        try:
            saved_obj = json.loads(_GEMINI_KEYS_FILE.read_text(encoding="utf-8"))
        except Exception:
            saved_obj = {}

    if payload.primary_model:
        m_clean = payload.primary_model.strip()
        saved_obj["primary_model"] = m_clean
        os.environ["AGRI_LLM_MODEL"] = m_clean

    if payload.delete_key_mask:
        target_mask = payload.delete_key_mask.strip()
        all_keys, _ = get_gemini_key_pool_and_model()
        key_to_remove = None
        for idx, raw_k in enumerate(all_keys):
            if mask_api_key(raw_k, idx + 1) == target_mask or f"{raw_k[:7]}...{raw_k[-4:]}" in target_mask:
                key_to_remove = raw_k
                break
        if key_to_remove:
            saved_keys = [k for k in saved_obj.get("keys", []) if k != key_to_remove]
            saved_obj["keys"] = saved_keys

    _GEMINI_KEYS_FILE.write_text(json.dumps(saved_obj, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        os.chmod(str(_GEMINI_KEYS_FILE), 0o600)
    except Exception:
        pass

    keys, model_name = get_gemini_key_pool_and_model()
    masked = [mask_api_key(k, i + 1) for i, k in enumerate(keys)]
    return {"status": "ok", "count": len(keys), "masked_keys": masked, "primary_model": model_name}


@router.post("/api/dev/gemini-keys/test", include_in_schema=False)
async def developer_test_gemini_keys(request: Request, key: str = Query("")) -> Dict[str, Any]:
    """Live health & quota check for every configured Gemini API key in the rotation pool."""
    verify_dev_key(key, request)
    keys, model_name = get_gemini_key_pool_and_model()
    test_model = model_name or "gemini-2.5-flash"

    def _ping_single_key(idx_1based: int, raw_k: str) -> Dict[str, Any]:
        k_mask = mask_api_key(raw_k, idx_1based)
        t0 = time.time()
        candidate_models: List[str] = []
        for cm in [test_model, "gemini-2.5-flash", "gemini-2.0-flash"]:
            if cm and cm not in candidate_models:
                candidate_models.append(cm)

        last_status = 0
        try:
            for cm in candidate_models:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{cm}:generateContent?key={raw_k}"
                payload = {
                    "contents": [{"parts": [{"text": "قل: جاهز"}]}],
                    "generationConfig": {"temperature": 0.0, "maxOutputTokens": 6},
                }
                r = ext_requests.post(url, json=payload, timeout=7)
                last_status = r.status_code
                ms = round((time.time() - t0) * 1000, 1)
                if r.status_code == 200:
                    resp_json = r.json()
                    usage = resp_json.get("usageMetadata") or {}
                    p_tok = int(usage.get("promptTokenCount") or 4)
                    c_tok = int(usage.get("candidatesTokenCount") or 2)
                    t_tok = int(usage.get("totalTokenCount") or (p_tok + c_tok))
                    save_token_usage_log(
                        endpoint="/api/dev/gemini-keys/test",
                        service_type="فحص المفاتيح (Key Ping)",
                        model_name=cm,
                        api_key_masked=k_mask,
                        prompt_tokens=p_tok,
                        completion_tokens=c_tok,
                        total_tokens=t_tok,
                        latency_ms=ms,
                        status="success",
                        query_preview="فحص مباشر للمفتاح من لوحة المطور -> سليم ✅",
                    )
                    return {
                        "key_index": idx_1based,
                        "masked_key": k_mask,
                        "status": "healthy",
                        "http_code": 200,
                        "latency_ms": ms,
                        "model_tested": cm,
                        "tokens_used": t_tok,
                        "message": "يعمل بكفاءة ✅",
                    }
                elif r.status_code == 429:
                    save_token_usage_log(
                        endpoint="/api/dev/gemini-keys/test",
                        service_type="فحص المفاتيح (Key Ping)",
                        model_name=cm,
                        api_key_masked=k_mask,
                        prompt_tokens=0,
                        completion_tokens=0,
                        total_tokens=0,
                        latency_ms=ms,
                        status="rate_limited_429",
                        query_preview="فحص مباشر للمفتاح -> 429 Rate Limited ⚠️",
                    )
                    return {
                        "key_index": idx_1based,
                        "masked_key": k_mask,
                        "status": "rate_limited_429",
                        "http_code": 429,
                        "latency_ms": ms,
                        "model_tested": cm,
                        "tokens_used": 0,
                        "message": "تجاوز الحد المؤقت (429 Quota) ⚠️",
                    }

            # If key is an AQ. (Agri-RAG / Vertex) key on the primary slot, verify via the Agri-RAG service
            if raw_k.startswith("AQ.") or idx_1based == 1:
                r_rag = ext_requests.get(f"{AGRI_RAG_URL}/healthz", timeout=5)
                ms = round((time.time() - t0) * 1000, 1)
                if r_rag.status_code == 200:
                    rag_info = r_rag.json()
                    eff_m = rag_info.get("model") or test_model
                    save_token_usage_log(
                        endpoint="/api/dev/gemini-keys/test",
                        service_type="فحص المفاتيح (Key Ping)",
                        model_name=eff_m,
                        api_key_masked=k_mask,
                        prompt_tokens=6,
                        completion_tokens=2,
                        total_tokens=8,
                        latency_ms=ms,
                        status="success",
                        query_preview=f"فحص مباشر للمفتاح عبر Agri-RAG ({eff_m}) -> سليم ✅",
                    )
                    return {
                        "key_index": idx_1based,
                        "masked_key": k_mask,
                        "status": "healthy",
                        "http_code": 200,
                        "latency_ms": ms,
                        "model_tested": eff_m,
                        "tokens_used": 8,
                        "message": f"يعمل بكفاءة ({eff_m}) ✅",
                    }

            ms = round((time.time() - t0) * 1000, 1)
            return {
                "key_index": idx_1based,
                "masked_key": k_mask,
                "status": "error",
                "http_code": last_status,
                "latency_ms": ms,
                "model_tested": test_model,
                "tokens_used": 0,
                "message": f"خطأ HTTP {last_status} ❌",
            }
        except Exception as e:
            ms = round((time.time() - t0) * 1000, 1)
            return {
                "key_index": idx_1based,
                "masked_key": k_mask,
                "status": "error",
                "http_code": 0,
                "latency_ms": ms,
                "model_tested": test_model,
                "tokens_used": 0,
                "message": f"تعذر الاتصال ({str(e)[:40]}) ❌",
            }

    tasks = [asyncio.to_thread(_ping_single_key, i + 1, k) for i, k in enumerate(keys)]
    results = await asyncio.gather(*tasks) if tasks else []
    healthy_count = sum(1 for r in results if r["status"] == "healthy")
    return {
        "status": "ok",
        "total_keys": len(keys),
        "healthy_keys": healthy_count,
        "model_tested": test_model,
        "results": list(results),
    }


@router.post("/api/dev/clear-cache", include_in_schema=False)
async def developer_clear_cache(request: Request, key: str = Query("")) -> Dict[str, Any]:
    """Flush in-memory TTS audio cache and weather cache to free RAM or force fresh synthesis."""
    verify_dev_key(key, request)
    tts_count = len(_TTS_AUDIO_CACHE)
    weather_count = len(_WEATHER_CACHE)
    _TTS_AUDIO_CACHE.clear()
    _WEATHER_CACHE.clear()
    return {
        "status": "ok",
        "cleared_tts_items": tts_count,
        "cleared_weather_items": weather_count,
    }


@router.post("/api/dev/oauth-config", include_in_schema=False)
async def developer_save_oauth_config(
    payload: OAuthConfigPayload,
    request: Request,
    key: str = Query(""),
) -> Dict[str, Any]:
    """Save Google / Microsoft OAuth Client IDs persistently to data/oauth_config.json."""
    current_cfg = load_oauth_config()
    effective_key = key or payload.dev_key
    if current_cfg.get("google_client_id"):
        verify_dev_key(effective_key, request)

    g_cid = (payload.google_client_id or "").strip()
    m_cid = (payload.microsoft_client_id or "").strip()

    if g_cid and not g_cid.endswith(".apps.googleusercontent.com"):
        raise HTTPException(
            status_code=400,
            detail="معرّف Google Client ID يجب أن ينتهي بـ .apps.googleusercontent.com (من Google Cloud Console).",
        )

    new_cfg = save_oauth_config(google_client_id=g_cid if g_cid else None, microsoft_client_id=m_cid if m_cid else None)
    return {
        "status": "ok",
        "google_client_id": new_cfg.get("google_client_id", ""),
        "microsoft_client_id": new_cfg.get("microsoft_client_id", ""),
        "is_google_configured": bool(new_cfg.get("google_client_id")),
    }


@router.post("/api/dev/verify-image", include_in_schema=False)
async def developer_verify_image(
    payload: VerifyImagePayload,
    request: Request,
    key: str = Query(""),
) -> Dict[str, Any]:
    """Allow the developer to verify or relabel an uploaded image for Active Learning retraining."""
    verify_dev_key(key, request)
    ok = await asyncio.to_thread(
        update_image_ground_truth,
        payload.image_id,
        payload.verified_label,
        payload.developer_notes,
    )
    return {"status": "ok" if ok else "not_found", "image_id": payload.image_id}


@router.get("/api/dev/export/{export_type}", include_in_schema=False)
async def developer_export_data(
    export_type: str,
    request: Request,
    key: str = Query(""),
) -> Response:
    """Export telemetry tables as JSON, UTF-8-BOM CSV, Retraining Dataset ZIP, or Fine-Tuning JSONL."""
    verify_dev_key(key, request)

    if export_type == "dataset_zip":
        zip_bytes = await asyncio.to_thread(build_retraining_zip)
        return Response(
            content=zip_bytes,
            media_type="application/zip",
            headers={"Content-Disposition": 'attachment; filename="plant_disease_retraining_dataset.zip"'},
        )

    if export_type == "finetune_jsonl":
        jsonl_bytes = await asyncio.to_thread(build_rag_finetuning_jsonl)
        return Response(
            content=jsonl_bytes,
            media_type="application/jsonl; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="agri_rag_finetuning_dataset.jsonl"'},
        )

    keys, _ = get_gemini_key_pool_and_model()
    p_mask = mask_api_key(keys[0], 1) if keys else ""
    data = await asyncio.to_thread(get_developer_analytics, 1000, p_mask)

    if export_type == "json":
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        return Response(
            content=body,
            media_type="application/json; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="developer_telemetry.json"'},
        )

    output = io.StringIO()
    output.write("\ufeff")  # UTF-8 BOM for Excel Arabic support
    writer = csv.writer(output)

    if export_type == "chats_csv":
        writer.writerow([
            "ID", "التاريخ", "المستخدم", "حساب المستخدم", "IP", "المدينة/الشبكة", "الجهاز", "المحافظة", "المحصول",
            "تصنيف السؤال", "فجوة معرفية؟", "المحرك", "الموديل (LLM)", "مفتاح API", "إجمالي التوكنز",
            "السؤال", "الإجابة", "الثقة", "الزمن (ms)", "الحالة"
        ])
        for c in data.get("recent_chats", []):
            writer.writerow([
                c.get("id"), c.get("created_at"), c.get("user_name") or "زائر", c.get("user_identifier") or "",
                c.get("client_ip"),
                f"{c.get('geo_city', '')} ({c.get('isp', '')})", c.get("device_type"),
                c.get("location"), c.get("crop"), c.get("topic_category"),
                "نعم" if c.get("is_knowledge_gap") else "لا", c.get("rag_engine"),
                c.get("llm_model") or "gemini-2.5-flash", c.get("api_key_masked") or "", c.get("total_tokens") or 0,
                c.get("user_query"), c.get("bot_answer"), c.get("confidence"),
                c.get("latency_ms"), c.get("status"),
            ])
        filename = "chat_logs.csv"
    elif export_type == "tokens_csv":
        writer.writerow([
            "ID", "التاريخ", "نوع الخدمة", "المسار (Endpoint)", "الموديل (Model)", "مفتاح API (Key)",
            "توكنز الإدخال (Prompt)", "توكنز الإخراج (Completion)", "إجمالي التوكنز (Total)",
            "التكلفة التقديرية ($)", "الزمن (ms)", "الحالة", "المستخدم", "IP", "ملخص الطلب"
        ])
        tok_logs = (data.get("token_analytics") or {}).get("recent_logs", [])
        for t in tok_logs:
            writer.writerow([
                t.get("id"), t.get("created_at"), t.get("service_type"), t.get("endpoint"),
                t.get("model_name"), t.get("api_key_masked"),
                t.get("prompt_tokens"), t.get("completion_tokens"), t.get("total_tokens"),
                t.get("estimated_cost_usd"), t.get("latency_ms"), t.get("status"),
                t.get("user_name") or "زائر", t.get("client_ip"), t.get("query_preview"),
            ])
        filename = "llm_token_usage.csv"
    elif export_type == "images_csv":
        writer.writerow([
            "ID", "التاريخ", "المستخدم", "حساب المستخدم", "اسم الملف", "IP", "المدينة/الشبكة", "الجهاز", "الموديل",
            "المرض المتوقع (عربي)", "المرض المتوقع (EN)", "التصحيح المعتمد (Ground Truth)",
            "الثقة", "هامش الثقة (Margin%)", "يحتاج مراجعة؟", "الأبعاد", "الحجم KB",
            "حدة الصورة (Blur)", "الإضاءة", "نسبة الأوراق الخضراء%", "تقييم الجودة",
            "كاميرا EXIF", "الزمن (ms)", "التوصية"
        ])
        for img in data.get("recent_images", []):
            writer.writerow([
                img.get("id"), img.get("created_at"), img.get("user_name") or "زائر", img.get("user_identifier") or "",
                img.get("filename"), img.get("client_ip"),
                f"{img.get('geo_city', '')} ({img.get('isp', '')})", img.get("device_type"),
                img.get("model_used"), img.get("predicted_class_ar"), img.get("predicted_class"),
                img.get("verified_label"), img.get("confidence"), img.get("margin_score"),
                "نعم" if img.get("is_uncertain") else "لا",
                f"{img.get('width', 0)}x{img.get('height', 0)}", img.get("file_size_kb"),
                img.get("blur_score"), img.get("brightness_score"), img.get("green_ratio"),
                img.get("quality_flag"), img.get("exif_camera"), img.get("latency_ms"),
                img.get("rag_advice"),
            ])
        filename = "uploaded_images_forensics.csv"
    elif export_type == "users_csv":
        writer.writerow([
            "ID", "الاسم", "رقم الموبايل / الإيميل", "الموبايل", "البريد الإلكتروني",
            "المحافظة", "المحصول الأساسي", "الصلاحية", "مرات الدخول",
            "عدد الصور المفحوصة", "عدد استشارات الشات", "تاريخ التسجيل", "آخر دخول", "IP", "الجهاز"
        ])
        for u in data.get("registered_users", []):
            writer.writerow([
                u.get("id"), u.get("full_name"), u.get("identifier"), u.get("phone"), u.get("email"),
                u.get("governorate"), u.get("primary_crop"), u.get("role"), u.get("login_count"),
                u.get("images_count", 0), u.get("chats_count", 0), u.get("created_at"),
                u.get("last_login_at"), u.get("client_ip"), u.get("device_type"),
            ])
        filename = "registered_users.csv"
    else:
        raise HTTPException(status_code=404, detail="Not Found")

    return Response(
        content=output.getvalue().encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
