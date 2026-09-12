# System Integration Architecture Document (بنية النظام المتكاملة)

This document presents the full technical architecture for the **Egyptian AI Farm-Management Platform**, detailing the integration between Computer Vision disease classification, the Egyptian Farming RAG Pipeline, and the Dashboard UI.

---

## 1. High-Level Integration Architecture

```
[ Farm Dashboard UI / Farmer App ]
                │  (POST /api/v1/diagnose-and-advise)
                ▼
┌────────────────────────────────────────────────────────┐
│             FastAPI Integration Gateway                │
│                    (app/main.py)                       │
├──────────────────────────┬─────────────────────────────┤
│ Computer Vision Service  │   Egyptian RAG Pipeline     │
│ (app/services/cv_service)│      (rag/respond.py)       │
│ - Leaf Preprocessing     │ - Orthography Normalization │
│ - Disease Classifier     │ - Dialect Canonicalization  │
│ - Confidence Scoring     │ - Intent Detection          │
│                          │ - Hybrid BM25 + Vector RRF  │
│                          │ - Vision Context Boosting   │
│                          │ - Grounded Advice LLM Gen   │
└──────────────────────────┴─────────────────────────────┘
                │                       │
                ▼                       ▼
    [ MLOps Model Registry ]   [ Prometheus / Grafana ]
    (mlops/model_registry)     (mlops/monitoring)
```

---

## 2. API Specifications & Endpoints

### `POST /api/v1/diagnose-and-advise`
Unified Integration Endpoint combining leaf diagnosis and grounded agricultural advice.

- **Request Format**: `multipart/form-data`
  - `farmer_query` (string, required): Inquiries in Egyptian farming Arabic (e.g. `"عندي ندوة متاخرة في البطاطس، ايه علاجها وايه جرعة الرشاش؟"`).
  - `image` (file, optional): Uploaded leaf/crop sample image.
  - `crop_override` (string, optional): Manual crop specification.
  - `region` (string, optional): Farming region in Egypt.

- **Response Payload Schema**:
```json
{
  "status": "success",
  "farmer_query": "عندي ندوة متاخرة في البطاطس، ايه علاجها وايه جرعة الرشاش؟",
  "processed_query": "عندي ندوة متاخرة في البطاطس، ايه علاجها وايه جرعه المبيد حشري؟",
  "intent": "dosage_lookup",
  "vision_prediction": {
    "crop_type": "potato",
    "disease_label": "late_blight",
    "confidence_score": 0.95,
    "bounding_box": [0.15, 0.2, 0.85, 0.9]
  },
  "answer": "بناءً على التوصيات المتاحة [مصدر 1]: يجب رش المبيد النحاسي...",
  "citations": [
    {
      "citation_tag": "[مصدر 1]",
      "chunk_id": "chunk-12345",
      "source_doc": "late_blight_protocol.txt",
      "doc_type": "protocol"
    }
  ],
  "retrieval_confidence": 0.92,
  "needs_agronomist_review": false,
  "latency_seconds": 0.045
}
```

### `GET /health`
Kubernetes Readiness/Liveness probe returning JSON service health.

### `GET /metrics`
Prometheus metrics export endpoint.
