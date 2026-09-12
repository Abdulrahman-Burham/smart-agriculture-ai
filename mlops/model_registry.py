"""MLOps Model Registry and Versioning System."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ModelRegistry:
    """Centralized MLOps registry tracking CV and Embedding model versions."""

    def __init__(self, registry_file: str | Path = "mlops/registry.json"):
        self.registry_file = Path(registry_file)
        self.registry_file.parent.mkdir(parents=True, exist_ok=True)
        self._load_registry()

    def _load_registry(self) -> None:
        if self.registry_file.exists():
            try:
                with open(self.registry_file, "r", encoding="utf-8") as f:
                    self.models = json.load(f)
            except Exception as err:
                logger.warning(f"Error loading model registry: {err}. Re-initializing.")
                self.models = {}
        else:
            self.models = {
                "cv_disease_classifier": {
                    "active_version": "v1.2.0",
                    "versions": {
                        "v1.2.0": {
                            "model_name": "crop_disease_resnet50",
                            "framework": "PyTorch",
                            "accuracy": 0.945,
                            "f1_score": 0.941,
                            "hash": "a8f9c1b3d4e5f67890abcdef12345678",
                            "stage": "production",
                            "created_at": time.time(),
                        }
                    },
                },
                "embedding_model": {
                    "active_version": "v1.0.0",
                    "versions": {
                        "v1.0.0": {
                            "model_name": "BAAI/bge-m3",
                            "framework": "HuggingFace",
                            "embedding_dim": 1024,
                            "stage": "production",
                            "created_at": time.time(),
                        }
                    },
                },
            }
            self._save_registry()

    def _save_registry(self) -> None:
        with open(self.registry_file, "w", encoding="utf-8") as f:
            json.dump(self.models, f, indent=2, ensure_ascii=False)

    def register_model_version(
        self,
        model_type: str,
        version: str,
        model_name: str,
        metrics: Dict[str, float],
        stage: str = "staging",
    ) -> Dict[str, Any]:
        """Register a new model version with metrics and staging tag."""
        if model_type not in self.models:
            self.models[model_type] = {"active_version": version, "versions": {}}

        version_info = {
            "model_name": model_name,
            "metrics": metrics,
            "stage": stage,
            "created_at": time.time(),
        }

        self.models[model_type]["versions"][version] = version_info
        if stage == "production":
            self.models[model_type]["active_version"] = version

        self._save_registry()
        logger.info(f"Registered model {model_type} version {version} ({stage})")
        return version_info

    def get_active_model(self, model_type: str) -> Optional[Dict[str, Any]]:
        """Retrieve current active production model version details."""
        if model_type not in self.models:
            return None
        active_ver = self.models[model_type].get("active_version")
        return self.models[model_type]["versions"].get(active_ver)
