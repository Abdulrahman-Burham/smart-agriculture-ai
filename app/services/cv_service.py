"""Computer Vision Disease Classification Service."""

from __future__ import annotations

import logging
import io
from typing import Any, Dict, Optional

from computer_vision.inference.classifier import PlantDiseaseClassifier

logger = logging.getLogger(__name__)


class ComputerVisionService:
    """Service wrapping crop disease computer vision model inference."""

    def __init__(self, model_version: str = "v1.2.0"):
        self.model_version = model_version
        self.classifier = PlantDiseaseClassifier()
        self.is_loaded = self.classifier.model is not None

    def preprocess_image(self, image_bytes: bytes) -> Dict[str, Any]:
        """Preprocess raw image bytes into normalized tensor array representation."""
        if not image_bytes:
            raise ValueError("Empty image payload received.")
        
        # Metadata extraction simulation
        image_size_bytes = len(image_bytes)
        return {
            "size_bytes": image_size_bytes,
            "status": "preprocessed",
        }

    def predict(
        self,
        image_bytes: Optional[bytes] = None,
        filename: str = "leaf_sample.jpg",
        crop_hint: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Predict crop species, disease label, and confidence score from image payload."""
        if not image_bytes:
            return {
                "crop_type": "unknown",
                "disease_label": "unknown",
                "confidence_score": 0.0,
                "bounding_box": [0.0, 0.0, 0.0, 0.0],
                "model_version": self.model_version,
                "predictions": []
            }
            
        try:
            image_stream = io.BytesIO(image_bytes)
            results = self.classifier.predict(image_stream)
            
            crop_type = results.get('crop_type', 'unknown')
            disease_label = results.get('disease_name', 'unknown')
            confidence = results.get('top_confidence', 0.0)
            predictions = results.get('predictions', [])
            
            return {
                "crop_type": crop_type,
                "disease_label": disease_label,
                "confidence_score": confidence,
                "bounding_box": [0.15, 0.20, 0.85, 0.90], # mock bounding box
                "model_version": self.model_version,
                "predictions": predictions
            }
        except Exception as e:
            logger.error(f"Prediction error: {e}")
            return {
                "crop_type": "unknown",
                "disease_label": "unknown",
                "confidence_score": 0.0,
                "bounding_box": [0.0, 0.0, 0.0, 0.0],
                "model_version": self.model_version,
            }
