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
    """Plant disease classifier matching AhmedHassan72/Zawolf_Agriculture HuggingFace Space 100%."""

    HF_SPACE_API = "https://ahmedhassan72-zawolf-agriculture.hf.space/predict"

    def __init__(self):
        self.use_keras_model = False
        self.best_model = None
        self.resnet_model = None
        self.resnet_classes = []
        self.resnet_tfm = None
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

        if model_choice == "ResNet18" and self.resnet_model is not None:
            import torch
            from PIL import Image
            img = Image.open(io.BytesIO(contents)).convert("RGB")
            with torch.inference_mode():
                probs = torch.softmax(self.resnet_model(self.resnet_tfm(img).unsqueeze(0)), dim=1)[0]
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
            crop_type, _ = self._parse_label(top_pred["label"])
            crop_ar, disease_ar = self._parse_label(top_pred["label_ar"])
            return {
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
        crop_type, _ = self._parse_label(top_pred["label"])
        crop_ar, disease_ar = self._parse_label(top_pred["label_ar"])

        return {
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
