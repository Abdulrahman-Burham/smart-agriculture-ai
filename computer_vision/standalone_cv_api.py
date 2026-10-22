from fastapi import FastAPI, UploadFile, File, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from typing import Literal
import numpy as np
import json
import os
import time

try:
    import tensorflow as tf
    import cv2

    HAS_TF_CV2 = True
except Exception:
    tf = None  # type: ignore[assignment]
    cv2 = None  # type: ignore[assignment]
    HAS_TF_CV2 = False

from computer_vision.db_storage import (
    init_db,
    save_image_record,
    save_visitor_log,
    save_error_log,
    extract_client_info,
)
from computer_vision.inference.classifier import ARABIC_CLASS_MAP, DEFAULT_CLASS_NAMES

app = FastAPI(title="Plant Disease Detection API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()


@app.middleware("http")
async def cv_silent_telemetry_middleware(request: Request, call_next):
    start_ts = time.time()
    client_info = extract_client_info(request)
    path = request.url.path
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    except Exception as exc:
        save_error_log(
            endpoint=f"/cv{path}",
            error=exc,
            status_code=500,
            client_ip=client_info["client_ip"],
            user_agent=client_info["user_agent"],
            device_type=client_info["device_type"],
        )
        raise
    finally:
        if path not in ("/health", "/favicon.ico"):
            latency_ms = round((time.time() - start_ts) * 1000, 2)
            save_visitor_log(
                method=request.method,
                path=f"/cv{path}" if not path.startswith("/cv") else path,
                status_code=status_code,
                latency_ms=latency_ms,
                query_string=str(request.url.query or ""),
                client_ip=client_info["client_ip"],
                visitor_hash=client_info["visitor_hash"],
                user_agent=client_info["user_agent"],
                device_type=client_info["device_type"],
                browser_os=client_info["browser_os"],
                referer=client_info["referer"],
            )


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "models", "EfficientNetV2B2_best.keras")
JSON_PATH = os.path.join(BASE_DIR, "models", "class_names.json")

best_model = None
if HAS_TF_CV2 and tf is not None:
    original_from_config = tf.keras.layers.Dense.from_config

    @classmethod
    def patched_from_config(cls, config):
        if isinstance(config, dict):
            config.pop("quantization_config", None)
        return original_from_config(config)

    tf.keras.layers.Dense.from_config = patched_from_config

    if os.path.exists(MODEL_PATH):
        try:
            best_model = tf.keras.models.load_model(MODEL_PATH)
            best_model.predict(np.zeros((1, 224, 224, 3), dtype=np.float32), verbose=0)
        except Exception:
            best_model = None

if os.path.exists(JSON_PATH):
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        class_names = json.load(f)
else:
    class_names = list(DEFAULT_CLASS_NAMES)

# Optional secondary model: ResNet18 (if available on server)
resnet_model = None
resnet_classes = []
resnet_tfm = None
RESNET_PATH = "/home/azureuser/plant-api/resnet18_plant_disease.pth"
RESNET_JSON = "/home/azureuser/plant-api/class_names.json"

try:
    if os.path.exists(RESNET_PATH) and os.path.exists(RESNET_JSON):
        import torch
        import torch.nn as nn
        from torchvision import models, transforms

        with open(RESNET_JSON, encoding="utf-8") as rf:
            resnet_classes = json.load(rf)["class_names"]
        _rm = models.resnet18(weights=None)
        _rm.fc = nn.Linear(_rm.fc.in_features, len(resnet_classes))
        _rm.load_state_dict(torch.load(resnet_path := RESNET_PATH, map_location="cpu"))
        _rm.eval()
        resnet_model = _rm
        resnet_tfm = transforms.Compose(
            [
                transforms.Resize((224, 224)),
                transforms.ToTensor(),
                transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
            ]
        )
except Exception as e:
    print(f"Optional ResNet18 not loaded: {e}")


@app.get("/")
def home():
    return {
        "message": "PlantVillage API is LIVE!",
        "default_model": "EfficientNetV2B2_best.keras",
        "available_models": ["EfficientNetV2B2"]
        + (["ResNet18"] if resnet_model is not None else []),
    }


@app.get("/health")
def health():
    return {
        "status": "online",
        "model_loaded": best_model is not None,
        "model_type": "EfficientNetV2B2_best.keras",
        "available_models": ["EfficientNetV2B2"]
        + (["ResNet18"] if resnet_model is not None else []),
        "num_classes": len(class_names),
    }


@app.post("/predict")
async def predict(
    request: Request,
    file: UploadFile = File(...),
    model_choice: Literal["EfficientNetV2B2", "ResNet18"] = Query(
        "EfficientNetV2B2",
        description="الموديل المستخدم للتشخيص (الافتراضي المثبت: EfficientNetV2B2)",
    ),
):
    start_ts = time.time()
    client_info = extract_client_info(request)
    try:
        contents = await file.read()

        # 1. First run the Strict Plant Gatekeeper (< 18% foliage rejection) & Crop Specialist Pipeline
        from app.services.vision_service import get_cv_classifier

        classifier = get_cv_classifier()
        cv_res = classifier.predict(contents, model_choice=model_choice)

        is_plant = cv_res.get("is_plant", True)
        if not is_plant or cv_res.get("predicted_class") == "Not_A_Plant":
            latency_ms = round((time.time() - start_ts) * 1000, 2)
            try:
                save_image_record(
                    image_bytes=contents,
                    filename=file.filename or "image.jpg",
                    content_type=file.content_type or "image/jpeg",
                    source_endpoint="/cv/predict",
                    model_used="Vision_Gatekeeper",
                    predicted_class="Not_A_Plant",
                    predicted_class_ar=cv_res.get(
                        "detected_object_ar", "صورة غير نباتية"
                    ),
                    confidence="0.00%",
                    top_predictions=[],
                    client_ip=client_info["client_ip"],
                    user_agent=client_info["user_agent"],
                    device_type=client_info["device_type"],
                    visitor_hash=client_info["visitor_hash"],
                    latency_ms=latency_ms,
                )
            except Exception as db_err:
                print(f"DB save warning: {db_err}")

            return {
                "status": "rejected",
                "is_plant": False,
                "predicted_class": "Not_A_Plant",
                "predicted_class_ar": cv_res.get(
                    "detected_object_ar", "صورة غير نباتية"
                ),
                "confidence": "0.00%",
                "top_predictions": [],
                "rejection_reason_ar": cv_res.get(
                    "rejection_reason_ar",
                    "تم رفض الصورة لأنها لا تحتوي على ورقة نبات واضحة أو نسبة المجموع الخضري ضئيلة جداً (< 18%)",
                ),
                "quality_flag": cv_res.get(
                    "quality_flag", "❌ نسبة نبات منخفضة جداً (غير صالحة للتشخيص)"
                ),
            }

        # 2. Plant confirmed -> Return specialist-isolated top predictions
        top_3_results = cv_res.get("top_predictions", [])
        top_cls = cv_res.get("predicted_class", "")
        latency_ms = round((time.time() - start_ts) * 1000, 2)
        try:
            save_image_record(
                image_bytes=contents,
                filename=file.filename or "image.jpg",
                content_type=file.content_type or "image/jpeg",
                source_endpoint="/cv/predict",
                model_used=cv_res.get("model_used", model_choice),
                predicted_class=top_cls,
                predicted_class_ar=cv_res.get(
                    "predicted_class_ar", ARABIC_CLASS_MAP.get(top_cls, top_cls)
                ),
                confidence=cv_res.get("confidence", "0.00%"),
                top_predictions=top_3_results,
                client_ip=client_info["client_ip"],
                user_agent=client_info["user_agent"],
                device_type=client_info["device_type"],
                visitor_hash=client_info["visitor_hash"],
                latency_ms=latency_ms,
            )
        except Exception as db_err:
            print(f"DB save warning: {db_err}")

        return {
            "status": "success",
            "is_plant": True,
            "crop": cv_res.get("crop"),
            "crop_ar": cv_res.get("crop_ar"),
            "predicted_class": top_cls,
            "predicted_class_ar": cv_res.get("predicted_class_ar"),
            "confidence": cv_res.get("confidence"),
            "top_predictions": top_3_results,
            "predictions": top_3_results,
        }

    except HTTPException:
        raise
    except Exception as e:
        save_error_log(
            endpoint="/cv/predict",
            error=e,
            status_code=500,
            client_ip=client_info["client_ip"],
            user_agent=client_info["user_agent"],
            device_type=client_info["device_type"],
            request_summary=f"filename={getattr(file, 'filename', '')}, model={model_choice}",
        )
        raise HTTPException(status_code=500, detail=str(e))
