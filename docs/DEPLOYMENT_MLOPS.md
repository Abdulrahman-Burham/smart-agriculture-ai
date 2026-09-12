# Production Deployment & MLOps Operational Guide (خطة وبيئة النشر و MLOps)

This guide documents continuous integration/deployment (CI/CD), Docker/Kubernetes container management, and MLOps model versioning workflows.

---

## 1. Local Development Stack (Docker Compose)

Launch the full integration gateway, Prometheus metrics collector, and Grafana monitoring dashboard:

```bash
docker-compose up --build -d
```

- **API Gateway**: `http://localhost:8000`
- **Interactive Swagger Docs**: `http://localhost:8000/docs`
- **Prometheus Metrics**: `http://localhost:9090`
- **Grafana Dashboard**: `http://localhost:3000` (admin/admin)

---

## 2. Kubernetes Production Deployment (AWS EKS / Azure AKS)

Apply Kubernetes manifests for HA deployment with Horizontal Pod Autoscaling (HPA):

```bash
# Apply deployment, loadbalancer service, and auto-scaler
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/hpa.yaml

# Verify pod status and HPA scaling limits
kubectl get pods -l app=agry-api-gateway
kubectl get hpa agry-api-gateway-hpa
```

### Auto-Scaling Rules
- **Minimum Replicas**: `2`
- **Maximum Replicas**: `10`
- **Target CPU Utilization**: `75%`
- **Target Memory Utilization**: `80%`

---

## 3. MLOps Model Versioning & Registry Workflows

Model versions are managed through [`mlops/model_registry.py`](file:///home/seg/Documents/agriculture/mlops/model_registry.py).

### Registering a New Model Version
```python
from mlops.model_registry import ModelRegistry

registry = ModelRegistry()
registry.register_model_version(
    model_type="cv_disease_classifier",
    version="v1.3.0",
    model_name="crop_disease_efficientnet_b4",
    metrics={"accuracy": 0.962, "f1_score": 0.958},
    stage="production"
)
```

---

## 4. Automated Testing & Quality Reporting

Execute test suites and generate QA quality reports:

```bash
# Run unit & E2E integration tests
PYTHONPATH=. ./venv/bin/pytest rag/tests/ tests/e2e/ -v

# Run load & stability performance test
PYTHONPATH=. ./venv/bin/python tests/load/test_load_performance.py

# Generate automated QA report
PYTHONPATH=. ./venv/bin/python scripts/generate_qa_report.py
```
