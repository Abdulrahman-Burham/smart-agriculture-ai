import io
import json
import os
import numpy as np

try:
    import tensorflow as tf
    import cv2
    HAS_TF_CV2 = True
except Exception:
    HAS_TF_CV2 = False

# Exact 30 MVP classes from Zawolf-Corpus-Classifiction.ipynb / HuggingFace Space
DEFAULT_CLASS_NAMES = [
    "Apple___Apple_scab",
    "Apple___Black_rot",
    "Apple___Cedar_apple_rust",
    "Apple___healthy",
    "Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot",
    "Corn_(maize)___Common_rust_",
    "Corn_(maize)___Northern_Leaf_Blight",
    "Corn_(maize)___healthy",
    "Grape___Black_rot",
    "Grape___Esca_(Black_Measles)",
    "Grape___Leaf_blight_(Isariopsis_Leaf_Spot)",
    "Grape___healthy",
    "Orange___Haunglongbing_(Citrus_greening)",
    "Pepper,_bell___Bacterial_spot",
    "Pepper,_bell___healthy",
    "Potato___Early_blight",
    "Potato___Late_blight",
    "Potato___healthy",
    "Strawberry___Leaf_scorch",
    "Strawberry___healthy",
    "Tomato___Bacterial_spot",
    "Tomato___Early_blight",
    "Tomato___Late_blight",
    "Tomato___Leaf_Mold",
    "Tomato___Septoria_leaf_spot",
    "Tomato___Spider_mites Two-spotted_spider_mite",
    "Tomato___Target_Spot",
    "Tomato___Tomato_Yellow_Leaf_Curl_Virus",
    "Tomato___Tomato_mosaic_virus",
    "Tomato___healthy",
]

ARABIC_CLASS_MAP = {
    "Apple___Apple_scab": "تفاح — جرب التفاح",
    "Apple___Black_rot": "تفاح — العفن الأسود",
    "Apple___Cedar_apple_rust": "تفاح — صدأ أرز التفاح",
    "Apple___healthy": "تفاح — سليم",
    "Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot": "ذرة — تبقع الأوراق الرمادي (سيركوسبورا)",
    "Corn_(maize)___Common_rust_": "ذرة — الصدأ الشائع",
    "Corn_(maize)___Northern_Leaf_Blight": "ذرة — لفحة الأوراق الشمالية",
    "Corn_(maize)___healthy": "ذرة — سليم",
    "Grape___Black_rot": "عنب — العفن الأسود",
    "Grape___Esca_(Black_Measles)": "عنب — مرض إسكا (الحصبة السوداء)",
    "Grape___Leaf_blight_(Isariopsis_Leaf_Spot)": "عنب — تبقع أوراق إيساريوبسيس",
    "Grape___healthy": "عنب — سليم",
    "Orange___Haunglongbing_(Citrus_greening)": "برتقال — مرض التخضير (تخضير الحمضيات)",
    "Pepper,_bell___Bacterial_spot": "فلفل حلو — التبقع البكتيري",
    "Pepper,_bell___healthy": "فلفل حلو — سليم",
    "Potato___Early_blight": "بطاطس — اللفحة المبكرة",
    "Potato___Late_blight": "بطاطس — اللفحة المتأخرة",
    "Potato___healthy": "بطاطس — سليم",
    "Strawberry___Leaf_scorch": "فراولة — حرق الأوراق",
    "Strawberry___healthy": "فراولة — سليم",
    "Tomato___Bacterial_spot": "طماطم — التبقع البكتيري",
    "Tomato___Early_blight": "طماطم — اللفحة المبكرة",
    "Tomato___Late_blight": "طماطم — اللفحة المتأخرة",
    "Tomato___Leaf_Mold": "طماطم — عفن الأوراق",
    "Tomato___Septoria_leaf_spot": "طماطم — تبقع أوراق سبتوريا",
    "Tomato___Spider_mites Two-spotted_spider_mite": "طماطم — العنكبوت الأحمر ذو البقعتين",
    "Tomato___Target_Spot": "طماطم — البقعة المستهدفة (التارجت)",
    "Tomato___Tomato_Yellow_Leaf_Curl_Virus": "طماطم — فيروس تجعد أوراق الطماطم الصفراء (TYLCV)",
    "Tomato___Tomato_mosaic_virus": "طماطم — فيروس الموزاييك",
    "Tomato___healthy": "طماطم — سليم",
}


class PlantDiseaseClassifier:
    """Plant disease classifier matching AhmedHassan72/Zawolf_Agriculture HuggingFace Space 100% + Non-Plant Filter."""

    HF_SPACE_API = "https://ahmedhassan72-zawolf-agriculture.hf.space/predict"

    def __init__(self):
        self.use_keras_model = False
        self.best_model = None
        self.resnet_model = None
        self.resnet_classes = []
        self.resnet_tfm = None
        self.face_cascade = None
        self.class_names = list(DEFAULT_CLASS_NAMES)
        self.class_names_ar = dict(ARABIC_CLASS_MAP)
        self._load_model()

    @property
    def model(self):
        return self.best_model if self.best_model is not None else True

    def _load_model(self):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        json_path = os.path.join(base_dir, "..", "models", "class_names.json")
        model_path = os.path.join(base_dir, "..", "models", "EfficientNetV2B2_best.keras")

        if HAS_TF_CV2:
            try:
                cascade_path = os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml")
                if os.path.exists(cascade_path):
                    self.face_cascade = cv2.CascadeClassifier(cascade_path)
            except Exception:
                self.face_cascade = None

        if os.path.exists(json_path):
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list) and len(data) == 30:
                    self.class_names = data

        if HAS_TF_CV2 and os.path.exists(model_path):
            original_from_config = tf.keras.layers.Dense.from_config
            @classmethod
            def patched_from_config(cls, config):
                if isinstance(config, dict):
                    config.pop("quantization_config", None)
                return original_from_config(config)
            tf.keras.layers.Dense.from_config = patched_from_config

            self.best_model = tf.keras.models.load_model(model_path)
            self.use_keras_model = True
            try:
                self.best_model.predict(np.zeros((1, 224, 224, 3), dtype=np.float32), verbose=0)
            except Exception:
                pass

        # Optional secondary model: ResNet18
        resnet_path = "/home/azureuser/plant-api/resnet18_plant_disease.pth"
        resnet_json = "/home/azureuser/plant-api/class_names.json"
        try:
            if os.path.exists(resnet_path) and os.path.exists(resnet_json):
                import torch
                import torch.nn as nn
                from torchvision import models, transforms
                with open(resnet_json, encoding="utf-8") as rf:
                    self.resnet_classes = json.load(rf)["class_names"]
                _rm = models.resnet18(weights=None)
                _rm.fc = nn.Linear(_rm.fc.in_features, len(self.resnet_classes))
                _rm.load_state_dict(torch.load(resnet_path, map_location="cpu"))
                _rm.eval()
                self.resnet_model = _rm
                self.resnet_tfm = transforms.Compose([
                    transforms.Resize((224, 224)),
                    transforms.ToTensor(),
                    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
                ])
        except Exception:
            pass

    def validate_plant_image_opencv(self, contents: bytes, top_conf: float = 1.0, norm_entropy: float = 0.0) -> dict:
        """Multi-signal visual gatekeeper to verify that the image contains a real plant/leaf and reject non-plant images."""
        res = {
            "is_plant": True,
            "green_foliage_pct": 25.0,
            "exg_pct": 25.0,
            "yellow_leaf_pct": 0.0,
            "face_area_pct": 0.0,
            "flat_ui_pct": 0.0,
            "detected_ar": "نبات / ورقة محصول",
            "reason_ar": "",
            "needs_gemini_check": False,
        }
        try:
            if not HAS_TF_CV2:
                return res
            nparr = np.frombuffer(contents, np.uint8)
            bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if bgr is None:
                return {
                    **res,
                    "is_plant": False,
                    "detected_ar": "ملف غير صالح",
                    "reason_ar": "الصورة المرفوعة تالفة أو غير صالحة.",
                }

            img256 = cv2.resize(bgr, (256, 256))
            gray = cv2.cvtColor(img256, cv2.COLOR_BGR2GRAY)
            hsv = cv2.cvtColor(img256, cv2.COLOR_BGR2HSV)

            b_ch = img256[:, :, 0].astype(np.float32)
            g_ch = img256[:, :, 1].astype(np.float32)
            r_ch = img256[:, :, 2].astype(np.float32)
            total_px = float(256 * 256)

            # 1. Strict green foliage (Hue 25..92 in OpenCV [0..179], Sat >= 26, Val >= 22, and G > R, G >= B)
            hsv_green = cv2.inRange(hsv, np.array([25, 26, 22]), np.array([92, 255, 255])) > 0
            rgb_green_dom = (g_ch > (r_ch + 3.0)) & (g_ch >= (b_ch + 2.0))
            strict_green_mask = hsv_green & rgb_green_dom
            green_foliage_pct = round(float(np.count_nonzero(strict_green_mask)) / total_px * 100.0, 2)

            # 2. ExG (Excess Green Index = 2G - R - B > 16)
            exg = (2.0 * g_ch) - r_ch - b_ch
            exg_mask = (exg > 16.0) & (g_ch > 32.0)
            exg_pct = round(float(np.count_nonzero(exg_mask)) / total_px * 100.0, 2)

            # 3. Chlorotic / Yellow / Brown necrotic leaf tissue (Hue 10..25, Sat >= 35, Val >= 28)
            yellow_mask = cv2.inRange(hsv, np.array([10, 35, 28]), np.array([25, 255, 240])) > 0
            yellow_leaf_pct = round(float(np.count_nonzero(yellow_mask)) / total_px * 100.0, 2)

            # 4. Flat UI / Screenshot / Document check (identical adjacent pixels + desaturated background)
            adj_same = np.all(img256[:, 1:, :] == img256[:, :-1, :], axis=-1)
            flat_ui_pct = round(float(np.count_nonzero(adj_same)) / float(256 * 255) * 100.0, 2)
            desat_mask = (hsv[:, :, 1] < 18) | (hsv[:, :, 2] > 244) | (hsv[:, :, 2] < 18)
            desat_pct = round(float(np.count_nonzero(desat_mask)) / total_px * 100.0, 2)

            # 5. Human Face Detection
            face_area_pct = 0.0
            if self.face_cascade is not None:
                faces = self.face_cascade.detectMultiScale(gray, scaleFactor=1.12, minNeighbors=5, minSize=(36, 36))
                if len(faces) > 0:
                    face_area_pct = round(sum(int(fw) * int(fh) for (_, _, fw, fh) in faces) / total_px * 100.0, 2)

            res.update({
                "green_foliage_pct": green_foliage_pct,
                "exg_pct": exg_pct,
                "yellow_leaf_pct": yellow_leaf_pct,
                "face_area_pct": face_area_pct,
                "flat_ui_pct": flat_ui_pct,
            })

            # Decision Rule A: Human Face / Selfie
            if face_area_pct >= 3.0 and green_foliage_pct < 22.0:
                res["is_plant"] = False
                res["detected_ar"] = "صورة شخصية / وجه إنسان"
                res["reason_ar"] = "الصورة المرفوعة تحتوي على شخص وليست ورقة نبات! هذا النظام مخصص فقط لفحص النباتات والمحاصيل الزراعية."
                return res

            # Decision Rule B: Screenshot / Text Document / Blank Screen / Digital Logo or Graphic
            if flat_ui_pct > 48.0 or ((flat_ui_pct > 35.0 or desat_pct > 76.0) and green_foliage_pct < 4.0 and exg_pct < 4.0):
                res["is_plant"] = False
                res["detected_ar"] = "لقطة شاشة (Screenshot) أو شعار رقمي أو مستند"
                res["reason_ar"] = "الصورة المرفوعة تبدو لقطة شاشة أو تصميماً رقمياً وليست صورة حقيقية لنبات! يرجى تصوير ورقة النبات الحقيقية بالكاميرا."
                return res

            # Decision Rule C: Zero or Near-Zero Plant Tissue (Cars, Animals, Buildings, Furniture, Electronics, etc.)
            if green_foliage_pct < 1.8 and exg_pct < 2.2:
                # Allow an exception only if it is a predominantly yellow/brown diseased leaf that still has traces of green and very high CV confidence
                is_yellow_diseased_leaf = (yellow_leaf_pct >= 24.0 and (green_foliage_pct >= 0.55 or exg_pct >= 0.75) and top_conf >= 0.78)
                if not is_yellow_diseased_leaf:
                    res["is_plant"] = False
                    res["detected_ar"] = "صورة غير نباتية (لا توجد أوراق أو أنسجة نباتية)"
                    res["reason_ar"] = "لم يتم رصد أي نبات أو أوراق خضراء في الصورة! النظام يقبل فقط صور أوراق النباتات والمحاصيل الزراعية."
                    return res

            # Decision Rule D: Weak Green + Low Classifier Confidence / High Uncertainty
            if green_foliage_pct < 6.0 and exg_pct < 6.0 and (top_conf < 0.52 or norm_entropy > 0.58):
                res["is_plant"] = False
                res["detected_ar"] = "جسم غير نباتي أو صورة غير واضحة"
                res["reason_ar"] = "الصورة لا تحتوي على ورقة نبات واضحة قابلة للتشخيص. يرجى تصوير ورقة النبات عن قرب."
                return res

            # Flag images that should be double-checked by Gemini Vision if available (e.g., green object or moderate foliage)
            if green_foliage_pct < 25.0 or top_conf < 0.85 or flat_ui_pct > 18.0 or face_area_pct > 0.0:
                res["needs_gemini_check"] = True

        except Exception:
            pass
        return res

    def _build_rejected_result(self, model_name: str, plant_check: dict) -> dict:
        detected = plant_check.get("detected_ar") or "صورة غير نباتية"
        reason = plant_check.get("reason_ar") or "هذا النظام يقبل فقط صور النباتات وأوراق المحاصيل الزراعية."
        return {
            "is_plant": False,
            "rejected": True,
            "detected_object_ar": detected,
            "rejection_reason_ar": reason,
            "plant_check": plant_check,
            "top_predictions": [],
            "predicted_class": "Not_A_Plant",
            "predicted_class_ar": f"⚠️ ليست صورة نبات ({detected})",
            "confidence": 0.0,
            "confidence_str": "مرفوضة",
            "predictions": [],
            "crop_type": "Non-Plant",
            "crop_type_ar": "❌ يقبل النباتات فقط",
            "disease_name": f"Not_A_Plant ({detected})",
            "top_confidence": 0.0,
            "model_used": model_name,
        }

    def predict(self, image_path_or_bytes, top_k=3, model_choice="EfficientNetV2B2"):
        if isinstance(image_path_or_bytes, str):
            with open(image_path_or_bytes, "rb") as f:
                contents = f.read()
        elif isinstance(image_path_or_bytes, bytes):
            contents = image_path_or_bytes
        else:
            if hasattr(image_path_or_bytes, "seek"):
                image_path_or_bytes.seek(0)
            contents = image_path_or_bytes.read()

        norm_entropy = 0.0

        if model_choice == "ResNet18" and self.resnet_model is not None:
            import torch
            from PIL import Image
            img = Image.open(io.BytesIO(contents)).convert("RGB")
            with torch.inference_mode():
                probs = torch.softmax(self.resnet_model(self.resnet_tfm(img).unsqueeze(0)), dim=1)[0]
            probs_np = probs.cpu().numpy()
            eps = 1e-9
            norm_entropy = float(-np.sum(probs_np * np.log(probs_np + eps)) / np.log(len(probs_np)))
            conf, idx = torch.topk(probs, min(top_k, len(probs)))
            top_3_results = []
            detailed_predictions = []
            for c, i in zip(conf, idx):
                raw_label = self.resnet_classes[int(i)]
                label_ar = self.class_names_ar.get(raw_label, raw_label)
                prob_val = float(c.item())
                confidence_val = float(prob_val * 100.0)
                top_3_results.append({
                    "class": raw_label,
                    "confidence": f"{confidence_val:.2f}%"
                })
                detailed_predictions.append({
                    "class": raw_label,
                    "label": raw_label,
                    "label_ar": label_ar,
                    "name": f"{raw_label} ({label_ar})",
                    "confidence": round(prob_val, 4),
                    "confidence_percent": round(confidence_val, 2),
                    "confidence_str": f"{confidence_val:.2f}%"
                })
            top_pred = detailed_predictions[0]
            plant_check = self.validate_plant_image_opencv(contents, top_conf=top_pred["confidence"], norm_entropy=norm_entropy)
            if not plant_check.get("is_plant", True):
                return self._build_rejected_result("ResNet18", plant_check)

            crop_type, _ = self._parse_label(top_pred["label"])
            crop_ar, disease_ar = self._parse_label(top_pred["label_ar"])
            return {
                "is_plant": True,
                "plant_check": plant_check,
                "top_predictions": top_3_results,
                "predicted_class": top_pred["label"],
                "predicted_class_ar": top_pred["label_ar"],
                "confidence": top_pred["confidence_percent"],
                "confidence_str": top_pred["confidence_str"],
                "predictions": detailed_predictions,
                "crop_type": crop_type,
                "crop_type_ar": crop_ar,
                "disease_name": f"{top_pred['label']} ({disease_ar})",
                "top_confidence": top_pred["confidence"],
                "model_used": "ResNet18",
            }

        if self.best_model is not None and HAS_TF_CV2:
            nparr = np.frombuffer(contents, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if image is None:
                raise ValueError("Invalid image file.")

            image_resized = cv2.resize(image, (224, 224))
            image_rgb = cv2.cvtColor(image_resized, cv2.COLOR_BGR2RGB)

            img_array = np.expand_dims(image_rgb, axis=0).astype(np.float32)
            predictions = self.best_model.predict(img_array, verbose=0)

            score = tf.nn.softmax(predictions[0]) if np.max(predictions[0]) > 1.0 else predictions[0]
            score_np = score.numpy() if hasattr(score, "numpy") else np.array(score)
            eps = 1e-9
            norm_entropy = float(-np.sum(score_np * np.log(score_np + eps)) / np.log(len(score_np)))

            top_indices = np.argsort(score_np)[::-1][:top_k]

            top_3_results = []
            detailed_predictions = []
            for idx in top_indices:
                raw_label = self.class_names[int(idx)]
                label_ar = self.class_names_ar.get(raw_label, raw_label)
                prob_val = float(score_np[idx])
                confidence_val = float(score_np[idx] * 100)
                top_3_results.append({
                    "class": raw_label,
                    "confidence": f"{confidence_val:.2f}%"
                })
                detailed_predictions.append({
                    "class": raw_label,
                    "label": raw_label,
                    "label_ar": label_ar,
                    "name": f"{raw_label} ({label_ar})",
                    "confidence": round(prob_val, 4),
                    "confidence_percent": round(confidence_val, 2),
                    "confidence_str": f"{confidence_val:.2f}%"
                })
        else:
            import requests
            r = requests.post(self.HF_SPACE_API, files={"file": ("image.jpg", contents, "image/jpeg")}, timeout=20)
            r.raise_for_status()
            top_3_results = r.json().get("top_predictions", [])
            detailed_predictions = []
            for item in top_3_results:
                raw_label = item["class"]
                conf_str = item["confidence"]
                conf_pct = float(conf_str.replace("%", ""))
                label_ar = self.class_names_ar.get(raw_label, raw_label)
                detailed_predictions.append({
                    "class": raw_label,
                    "label": raw_label,
                    "label_ar": label_ar,
                    "name": f"{raw_label} ({label_ar})",
                    "confidence": round(conf_pct / 100.0, 4),
                    "confidence_percent": round(conf_pct, 2),
                    "confidence_str": conf_str
                })

        top_pred = detailed_predictions[0]
        plant_check = self.validate_plant_image_opencv(contents, top_conf=top_pred["confidence"], norm_entropy=norm_entropy)
        if not plant_check.get("is_plant", True):
            return self._build_rejected_result("EfficientNetV2B2_best.keras", plant_check)

        crop_type, _ = self._parse_label(top_pred["label"])
        crop_ar, disease_ar = self._parse_label(top_pred["label_ar"])

        return {
            "is_plant": True,
            "plant_check": plant_check,
            "top_predictions": top_3_results,
            "predicted_class": top_pred["label"],
            "predicted_class_ar": top_pred["label_ar"],
            "confidence": top_pred["confidence_percent"],
            "confidence_str": top_pred["confidence_str"],
            "predictions": detailed_predictions,
            "crop_type": crop_type,
            "crop_type_ar": crop_ar,
            "disease_name": f"{top_pred['label']} ({disease_ar})",
            "top_confidence": top_pred["confidence"],
            "model_used": "EfficientNetV2B2_best.keras",
        }

    def _parse_label(self, label):
        if "—" in label:
            parts = label.split("—")
            return parts[0].strip(), parts[1].strip()
        elif "___" in label:
            parts = label.split("___")
            return parts[0].strip(), parts[1].strip().replace("_", " ")
        return label, "unknown"
