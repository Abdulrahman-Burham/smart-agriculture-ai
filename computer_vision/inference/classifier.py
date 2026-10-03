import torch
from PIL import Image
from transformers import AutoModelForImageClassification, AutoImageProcessor, AutoFeatureExtractor
from torchvision import transforms
import json
import os

class PlantDiseaseClassifier:
    """Real plant disease classifier using MobileNetV2 fine-tuned on PlantVillage."""
    
    # Use a known working HuggingFace model for plant disease
    MODEL_NAME = "linkanjarad/mobilenet_v2_1.0_224-plant-disease-identification"
    
    def __init__(self):
        self.model = None
        self.processor = None
        self.transform = None
        self.class_names_ar = {}  # Arabic translations
        self._load_model()
    
    def _load_model(self):
        """Load model from HuggingFace hub (auto-cached locally)."""
        try:
            self.model = AutoModelForImageClassification.from_pretrained(self.MODEL_NAME)
            self.model.eval()

            try:
                self.processor = AutoImageProcessor.from_pretrained(self.MODEL_NAME)
            except Exception:
                try:
                    self.processor = AutoFeatureExtractor.from_pretrained(self.MODEL_NAME)
                except Exception:
                    self.processor = None

            # Fallback torchvision transform if processor is missing/fails
            self.transform = transforms.Compose([
                transforms.Resize((224, 224)),
                transforms.ToTensor(),
                transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
            ])
            
            # Load Arabic class names
            class_names_path = os.path.join(os.path.dirname(__file__), '..', 'models', 'class_names.json')
            if os.path.exists(class_names_path):
                with open(class_names_path, 'r', encoding='utf-8') as f:
                    self.class_names_ar = json.load(f)
        except Exception as e:
            print(f"Warning: Could not load plant disease model: {e}")
            self.model = None
    
    def predict(self, image_path_or_bytes, top_k=3):
        """Predict plant disease from an image.
        
        Args:
            image_path_or_bytes: File path string or bytes-like file object
            top_k: Number of top predictions to return
            
        Returns:
            dict with keys: predictions (list of {label, label_ar, confidence}), crop_type, disease_name
        """
        if self.model is None:
            return self._fallback_prediction()
        
        try:
            # Load image
            if isinstance(image_path_or_bytes, str):
                image = Image.open(image_path_or_bytes).convert('RGB')
            else:
                image = Image.open(image_path_or_bytes).convert('RGB')
            
            # Preprocess
            if self.processor is not None:
                inputs = self.processor(images=image, return_tensors='pt')
            else:
                inputs = {'pixel_values': self.transform(image).unsqueeze(0)}
            
            # Inference
            with torch.no_grad():
                outputs = self.model(**inputs)
                logits = outputs.logits
                probs = torch.nn.functional.softmax(logits, dim=-1)
            
            # Get top-k predictions
            top_probs, top_indices = torch.topk(probs[0], min(top_k, len(probs[0])))
            
            predictions = []
            for prob, idx in zip(top_probs, top_indices):
                label = self.model.config.id2label.get(idx.item(), f"class_{idx.item()}")
                label_ar = self.class_names_ar.get(label, label)
                predictions.append({
                    'label': label,
                    'label_ar': label_ar,
                    'confidence': round(prob.item(), 4)
                })
            
            # Extract crop and disease from top prediction
            top_label = predictions[0]['label'] if predictions else 'unknown'
            crop_type, disease_name = self._parse_label(top_label)
            
            return {
                'predictions': predictions,
                'crop_type': crop_type,
                'disease_name': disease_name,
                'top_confidence': predictions[0]['confidence'] if predictions else 0.0
            }
        except Exception as e:
            print(f"Prediction error: {e}")
            return self._fallback_prediction()
    
    def _parse_label(self, label):
        """Parse PlantVillage label format 'Crop___Disease' into (crop, disease)."""
        if '___' in label:
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
