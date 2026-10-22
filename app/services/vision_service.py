"""Vision Service: Plant Disease Classification & Gemini Plant Gatekeeper.

Provides:
- Lazy singleton loader for the local computer vision model (`get_cv_classifier`)
- Dual-layer plant verification: OpenCV multi-signal filter + Gemini Vision Gatekeeper
- Upload limits and image preprocessing helpers
"""

from __future__ import annotations

import base64
import logging
import time
from typing import Any, Dict, List, Optional

import requests as ext_requests

from app.services.llm_service import get_gemini_key_pool_and_model
from computer_vision.storage.telemetry_repository import save_token_usage_log
from computer_vision.storage.utils import mask_api_key

logger = logging.getLogger(__name__)

MAX_UPLOAD_BYTES: int = 15 * 1024 * 1024  # 15 MB

_cv_classifier: Optional[Any] = None
_VISION_KEY_RR_IDX: int = 0

PLANT_GATEKEEPER_PROMPT: str = (
    "Look carefully at this uploaded image.\n"
    "Determine whether the image shows a REAL plant, crop leaf, tree, plant stem, fruit/vegetable on a plant, or agricultural foliage.\n"
    "If it is NOT a plant (for example: a human face/selfie/person, animal, car, room, furniture, computer/phone screen, screenshot, document, clothing, logo, cartoon, food plate, or random object), reject it.\n"
    "Reply with ONLY ONE LINE in this exact format:\n"
    "PLANT|ورقة نبات\n"
    "OR if it is not a plant:\n"
    "NOT_PLANT|<short Arabic name of what is in the photo, e.g. صورة شخص / سيارة / قطة / لقطة شاشة / غرفة / ملابس / جسم غير نباتي>"
)


def get_cv_classifier() -> Optional[Any]:
    """Lazily initialize and return the CV classifier singleton."""
    global _cv_classifier
    if _cv_classifier is None:
        try:
            from computer_vision.inference.classifier import PlantDiseaseClassifier

            _cv_classifier = PlantDiseaseClassifier()
            logger.info("🌿 Plant Disease CV Model loaded successfully.")
        except Exception as e:
            logger.warning(f"⚠️ CV Model not available: {e}")
            _cv_classifier = "unavailable"

    if _cv_classifier == "unavailable":
        return None
    return _cv_classifier


def verify_plant_image_gemini_sync(
    image_bytes: bytes, mime_type: str = "image/jpeg"
) -> Dict[str, Any]:
    """Fast Gemini Vision gatekeeper (runs in parallel with CV classifier) to reject non-plant images."""
    global _VISION_KEY_RR_IDX

    keys, cfg_model = get_gemini_key_pool_and_model()
    if not keys:
        return {"checked": False, "is_plant": True, "detected_ar": ""}

    n_keys = len(keys)
    start_idx = _VISION_KEY_RR_IDX % n_keys
    _VISION_KEY_RR_IDX += 1
    ordered_pairs = [
        ((start_idx + i) % n_keys + 1, keys[(start_idx + i) % n_keys])
        for i in range(n_keys)
    ]

    b64_img = base64.b64encode(image_bytes).decode("ascii")
    clean_mime = (mime_type or "image/jpeg").split(";")[0].strip()
    if clean_mime not in ("image/jpeg", "image/png", "image/webp"):
        clean_mime = "image/jpeg"

    models = [cfg_model, "gemini-2.5-flash", "gemini-2.0-flash"]
    seen_m: List[str] = []
    for m in models:
        if m and m not in seen_m:
            seen_m.append(m)

    for k_idx, api_key in ordered_pairs[:2]:
        key_mask = mask_api_key(api_key, k_idx)
        for m in seen_m[:1]:
            t0 = time.time()
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={api_key}"
                payload = {
                    "contents": [
                        {
                            "parts": [
                                {"text": PLANT_GATEKEEPER_PROMPT},
                                {
                                    "inlineData": {
                                        "mimeType": clean_mime,
                                        "data": b64_img,
                                    }
                                },
                            ]
                        }
                    ],
                    "generationConfig": {"temperature": 0.0, "maxOutputTokens": 40},
                }
                r = ext_requests.post(url, json=payload, timeout=3.8)
                call_ms = round((time.time() - t0) * 1000, 1)
                if r.status_code == 200:
                    resp_json = r.json()
                    usage = resp_json.get("usageMetadata") or {}
                    p_tok = int(usage.get("promptTokenCount") or 320)
                    c_tok = int(usage.get("candidatesTokenCount") or 12)
                    t_tok = int(usage.get("totalTokenCount") or (p_tok + c_tok))
                    candidates = resp_json.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts and parts[0].get("text"):
                            ans = parts[0]["text"].strip()
                            save_token_usage_log(
                                endpoint="/api/diagnose (Gatekeeper)",
                                service_type="vision_gatekeeper",
                                model_name=m,
                                api_key_masked=key_mask,
                                prompt_tokens=p_tok,
                                completion_tokens=c_tok,
                                total_tokens=t_tok,
                                latency_ms=call_ms,
                                status="success",
                                query_preview=f"Plant Gatekeeper -> {ans[:80]}",
                            )
                            upper_ans = ans.upper()
                            if (
                                upper_ans.startswith("NOT_PLANT")
                                or "NOT_PLANT" in upper_ans
                            ):
                                det = "جسم غير نباتي"
                                if "|" in ans:
                                    det = ans.split("|", 1)[1].strip() or det
                                return {
                                    "checked": True,
                                    "is_plant": False,
                                    "detected_ar": det,
                                }
                            if upper_ans.startswith("PLANT"):
                                return {
                                    "checked": True,
                                    "is_plant": True,
                                    "detected_ar": "نبات",
                                }
                elif r.status_code == 429:
                    save_token_usage_log(
                        endpoint="/api/diagnose (Gatekeeper)",
                        service_type="vision_gatekeeper",
                        model_name=m,
                        api_key_masked=key_mask,
                        prompt_tokens=0,
                        completion_tokens=0,
                        total_tokens=0,
                        latency_ms=call_ms,
                        status="rate_limited_429",
                        query_preview="HTTP 429 Rate Limit on Gatekeeper",
                    )
            except Exception:
                pass

    return {"checked": False, "is_plant": True, "detected_ar": ""}
