import os
import json
import numpy as np
from PIL import Image

# Ensure KERAS_BACKEND is set to torch for fast PyTorch execution
os.environ["KERAS_BACKEND"] = "torch"

try:
    import keras
    HAS_KERAS = True
except Exception:
    HAS_KERAS = False

import torch
from torchvision import transforms
from transformers import AutoModelForImageClassification, AutoImageProcessor, AutoFeatureExtractor


class PlantDiseaseClassifier:
    """Plant disease classifier supporting custom fine-tuned EfficientNetV2B2 and MobileNetV2 fallback."""

    HF_MODEL_NAME = "linkanjarad/mobilenet_v2_1.0_224-plant-disease-identification"

    def __init__(self):
        self.use_keras_model = False
        self.keras_model = None
        self.hf_model = None
        self.processor = None
        self.transform = None
        self.class_names_ar = {}
        self._load_model()

    @property
    def model(self):
        """Property for backwards compatibility with health checks."""
        return self.keras_model if self.use_keras_model else self.hf_model

    def _load_model(self):
        """Load fine-tuned EfficientNetV2B2 Keras model if available, otherwise HuggingFace model."""
        # 1. Load Arabic class names mapping
        class_names_path = os.path.join(os.path.dirname(__file__), '..', 'models', 'class_names.json')
        if os.path.exists(class_names_path):
            try:
                with open(class_names_path, 'r', encoding='utf-8') as f:
                    self.class_names_ar = json.load(f)
            except Exception as e:
                print(f"Warning: Failed loading class_names.json: {e}")

        # 2. Try loading local custom Keras EfficientNetV2B2 model
        keras_model_path = os.path.join(os.path.dirname(__file__), '..', 'models', 'EfficientNetV2B2_best.keras')
        if HAS_KERAS and os.path.exists(keras_model_path):
            try:
                print(f"Loading custom fine-tuned EfficientNetV2B2 model from {keras_model_path}...")
                self.keras_model = keras.models.load_model(keras_model_path, compile=False)
                self.use_keras_model = True
                print("✅ EfficientNetV2B2 Keras model loaded successfully!")
                return
            except Exception as e:
                print(f"Warning: Failed to load custom Keras model: {e}")
                self.keras_model = None
                self.use_keras_model = False

        # 3. Fallback: Load HuggingFace MobileNetV2 model
        try:
            print("Loading HuggingFace MobileNetV2 fallback model...")
            self.hf_model = AutoModelForImageClassification.from_pretrained(self.HF_MODEL_NAME)
            self.hf_model.eval()

            try:
                self.processor = AutoImageProcessor.from_pretrained(self.HF_MODEL_NAME)
            except Exception:
                try:
                    self.processor = AutoFeatureExtractor.from_pretrained(self.HF_MODEL_NAME)
                except Exception:
                    self.processor = None

            self.transform = transforms.Compose([
                transforms.Resize((224, 224)),
                transforms.ToTensor(),
                transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
            ])
        except Exception as e:
            print(f"Warning: Could not load HuggingFace fallback model: {e}")
            self.hf_model = None

    def predict(self, image_path_or_bytes, top_k=3):
        """Predict plant disease from an image payload.
        
        Args:
            image_path_or_bytes: File path string or BytesIO/bytes file object
            top_k: Number of top predictions to return
            
        Returns:
            dict with keys: predictions (list of {label, label_ar, confidence}), crop_type, disease_name
        """
        if not self.use_keras_model and self.hf_model is None:
            return self._fallback_prediction()

        try:
            # Load PIL Image
            if isinstance(image_path_or_bytes, str):
                image = Image.open(image_path_or_bytes).convert('RGB')
            elif isinstance(image_path_or_bytes, bytes):
                import io
                image = Image.open(io.BytesIO(image_path_or_bytes)).convert('RGB')
            else:
                image = Image.open(image_path_or_bytes).convert('RGB')

            if self.use_keras_model and self.keras_model is not None:
                # EfficientNetV2B2 Keras prediction
                resized_img = image.resize((224, 224))
                img_array = np.array(resized_img, dtype=np.float32)
                img_batch = np.expand_dims(img_array, axis=0) # (1, 224, 224, 3)

                probs = self.keras_model.predict(img_batch, verbose=0)[0]
                top_indices = np.argsort(probs)[::-1][:top_k]

                predictions = []
                for idx in top_indices:
                    prob = float(probs[idx])
                    label = f"class_{idx}"
                    label_ar = self.class_names_ar.get(label, self.class_names_ar.get(str(idx), f"فئة زراعية #{idx}"))
                    predictions.append({
                        'label': label_ar if label_ar else label,
                        'label_ar': label_ar,
                        'confidence': round(prob, 4)
                    })

                top_label = predictions[0]['label_ar'] if predictions else 'unknown'
                crop_type, disease_name = self._parse_label(top_label)

                return {
                    'predictions': predictions,
                    'crop_type': crop_type,
                    'disease_name': disease_name,
                    'top_confidence': predictions[0]['confidence'] if predictions else 0.0,
                    'model_used': 'EfficientNetV2B2_best'
                }
            else:
                # HuggingFace MobileNetV2 prediction
                if self.processor is not None:
                    inputs = self.processor(images=image, return_tensors='pt')
                else:
                    inputs = {'pixel_values': self.transform(image).unsqueeze(0)}

                with torch.no_grad():
                    outputs = self.hf_model(**inputs)
                    logits = outputs.logits
                    probs = torch.nn.functional.softmax(logits, dim=-1)

                top_probs, top_indices = torch.topk(probs[0], min(top_k, len(probs[0])))

                predictions = []
                for prob, idx in zip(top_probs, top_indices):
                    label = self.hf_model.config.id2label.get(idx.item(), f"class_{idx.item()}")
                    label_ar = self.class_names_ar.get(label, label)
                    predictions.append({
                        'label': label,
                        'label_ar': label_ar,
                        'confidence': round(prob.item(), 4)
                    })

                top_label = predictions[0]['label'] if predictions else 'unknown'
                crop_type, disease_name = self._parse_label(top_label)

                return {
                    'predictions': predictions,
                    'crop_type': crop_type,
                    'disease_name': disease_name,
                    'top_confidence': predictions[0]['confidence'] if predictions else 0.0,
                    'model_used': 'MobileNetV2_HuggingFace'
                }
        except Exception as e:
            print(f"Prediction error: {e}")
            return self._fallback_prediction()

    def _parse_label(self, label):
        """Parse PlantVillage label format 'Crop___Disease' into (crop, disease)."""
        if '—' in label:
            parts = label.split('—')
            return parts[0].strip(), parts[1].strip()
        elif '___' in label:
            parts = label.split('___')
            return parts[0].strip(), parts[1].strip().replace('_', ' ')
        elif '__' in label:
            parts = label.split('__')
            return parts[0].strip(), parts[1].strip().replace('_', ' ')
        return label, 'unknown'

    def _fallback_prediction(self):
        """Return a safe fallback when model is unavailable."""
        return {
            'predictions': [{'label': 'model_unavailable', 'label_ar': 'النموذج غير متاح', 'confidence': 0.0}],
            'crop_type': 'unknown',
            'disease_name': 'unknown',
            'top_confidence': 0.0
        }
