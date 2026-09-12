"""MLOps Command Line Interface (CLI) Utility for Model Versioning & Monitoring."""

from __future__ import annotations

import sys
import json
import argparse
from typing import Any, Dict

from mlops.model_registry import ModelRegistry
from mlops.monitoring import SystemMonitor


def list_models(registry: ModelRegistry) -> None:
    """Print all registered model artifacts and active versions."""
    print("=" * 60)
    print("📦 MLOps Model Registry Overview")
    print("=" * 60)
    for model_type, data in registry.models.items():
        print(f"\n🔹 Model Type: {model_type}")
        print(f"   Active Version: {data.get('active_version')}")
        print("   Registered Versions:")
        for ver, details in data.get("versions", {}).items():
            print(f"     - [{ver}] Stage: {details.get('stage')} | Metrics: {details.get('metrics') or details.get('accuracy')}")


def promote_model(registry: ModelRegistry, model_type: str, version: str) -> None:
    """Promote a specific model version to production stage."""
    if model_type not in registry.models or version not in registry.models[model_type]["versions"]:
        print(f"❌ Error: Version '{version}' for model '{model_type}' not found in registry.")
        sys.exit(1)

    # Set previous production model stage to archived
    for v_name, v_data in registry.models[model_type]["versions"].items():
        if v_data.get("stage") == "production":
            v_data["stage"] = "archived"

    registry.models[model_type]["versions"][version]["stage"] = "production"
    registry.models[model_type]["active_version"] = version
    registry._save_registry()

    print(f"🚀 Successfully promoted {model_type}:{version} to PRODUCTION stage!")


def check_system_monitoring(monitor: SystemMonitor) -> None:
    """Print system latency, request metrics, and concept drift status."""
    stats = monitor.get_summary_statistics()
    print("=" * 60)
    print("📊 Real-Time System Monitoring & Drift Status")
    print("=" * 60)
    print(json.dumps(stats, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Egyptian Agricultural Platform MLOps CLI Tool")
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # List models command
    subparsers.add_parser("list", help="List registered models and active production versions")

    # Promote model command
    promote_parser = subparsers.add_parser("promote", help="Promote a model version to production")
    promote_parser.add_argument("--model", required=True, help="Model type (e.g. cv_disease_classifier)")
    promote_parser.add_argument("--version", required=True, help="Target version string (e.g. v1.2.0)")

    # Monitoring command
    subparsers.add_parser("monitor", help="Check live system metrics and concept drift alerts")

    args = parser.parse_args()

    registry = ModelRegistry()
    monitor = SystemMonitor()

    if args.command == "list" or not args.command:
        list_models(registry)
    elif args.command == "promote":
        promote_model(registry, args.model, args.version)
    elif args.command == "monitor":
        check_system_monitoring(monitor)


if __name__ == "__main__":
    main()
