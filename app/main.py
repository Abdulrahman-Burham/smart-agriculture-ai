"""FastAPI Integration Gateway Service connecting Computer Vision, Egyptian RAG Pipeline, and Dashboard UI."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import FileResponse, Response

from app.schemas import (
    CitationItem,
    DiagnoseAndAdviseRequest,
    DiagnoseAndAdviseResponse,
    HealthCheckResponse,
    VisionPredictionResult,
)
from app.services.cv_service import ComputerVisionService
from mlops.model_registry import ModelRegistry
from mlops.monitoring import SystemMonitor
from rag.respond import RAGPipeline

logger = logging.getLogger(__name__)

# Initialize FastAPI Gateway Application
app = FastAPI(
    title="Egyptian Agricultural AI Platform API Gateway",
    description="Unified API Gateway integrating Computer Vision, Egyptian Farming RAG Pipeline, and Dashboard UI.",
    version="1.0.0",
)

# Configure CORS Middleware for Dashboard Web UI Integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Static Web Dashboard Interface
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/", include_in_schema=False)
@app.get("/dashboard", include_in_schema=False)
def serve_dashboard():
    """Serve the Web Dashboard UI interface."""
    return FileResponse("app/static/index.html")

# Core Microservice Instances
cv_service = ComputerVisionService()
rag_pipeline = RAGPipeline()
model_registry = ModelRegistry()
system_monitor = SystemMonitor()


@app.on_event("startup")
def auto_ingest_knowledge_base():
    """Auto-ingest sample agricultural knowledge base on startup if directory exists."""
    from pathlib import Path
    data_dir = Path("data/sample_knowledge_base")
    if data_dir.exists():
        docs = []
        for p in data_dir.glob("*.txt"):
            docs.append({
                "source_doc": p.name,
                "doc_type": "protocol" if "protocol" in p.name.lower() else "guide",
                "crop_type": "potato" if "potato" in p.name.lower() else "general",
                "disease_name": "general",
                "region": "egypt_general",
                "content": p.read_text(encoding="utf-8"),
            })
        if docs:
            rag_pipeline.ingest_documents(docs)
            logger.info(f"Auto-ingested {len(docs)} documents into knowledge base on startup.")

    uploaded_dir = Path("data/uploaded_pdfs")
    uploaded_pdfs = sorted(uploaded_dir.glob("*.pdf")) if uploaded_dir.exists() else []
    if uploaded_pdfs:
        summary = rag_pipeline.ingest_pdfs([str(path) for path in uploaded_pdfs])
        logger.info(
            "Auto-ingested uploaded PDFs: %s files, %s documents, %s chunks.",
            summary["num_pdfs"],
            summary["num_documents"],
            summary["num_chunks"],
        )


@app.get("/health", response_model=HealthCheckResponse, tags=["System Health"])
def health_check() -> HealthCheckResponse:
    """Readiness and Liveness probe for Kubernetes pod orchestration."""
    return HealthCheckResponse(
        status="healthy",
        services={
            "api_gateway": "online",
            "cv_service": "online" if cv_service.is_loaded else "offline",
            "rag_pipeline": "online",
            "vector_store": "online",
        },
        version="1.0.0",
    )


@app.get("/metrics", tags=["Monitoring"])
def metrics() -> Response:
    """Expose Prometheus real-time operational metrics."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/api/v1/cv/predict", response_model=VisionPredictionResult, tags=["Computer Vision"])
async def predict_crop_disease(
    image: UploadFile = File(...),
    crop_hint: Optional[str] = Form(None),
) -> VisionPredictionResult:
    """Standalone Computer Vision model inference endpoint for image disease identification."""
    try:
        contents = await image.read()
        prediction = cv_service.predict(image_bytes=contents, filename=image.filename, crop_hint=crop_hint)
        return VisionPredictionResult(
            crop_type=prediction["crop_type"],
            disease_label=prediction["disease_label"],
            confidence_score=prediction["confidence_score"],
            bounding_box=prediction.get("bounding_box"),
        )
    except Exception as err:
        logger.error(f"Computer Vision prediction error: {err}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(err))


@app.post(
    "/api/v1/diagnose-and-advise",
    response_model=DiagnoseAndAdviseResponse,
    tags=["Integration Gateway"],
)
async def diagnose_and_advise(
    farmer_query: str = Form(...),
    image: Optional[UploadFile] = File(None),
    crop_override: Optional[str] = Form(None),
    disease_override: Optional[str] = Form(None),
    region: Optional[str] = Form("egypt_general"),
) -> DiagnoseAndAdviseResponse:
    """Unified integration endpoint: processes crop leaf image + query, runs RAG retrieval, returns advice."""
    start_time = time.time()

    try:
        # 1. Computer Vision Image Inference (if image payload attached)
        vision_prediction_payload: Optional[Dict[str, Any]] = None
        vision_result_schema: Optional[VisionPredictionResult] = None

        if image is not None:
            image_bytes = await image.read()
            if len(image_bytes) > 0:
                vision_prediction_payload = cv_service.predict(
                    image_bytes=image_bytes, filename=image.filename, crop_hint=crop_override
                )
                vision_result_schema = VisionPredictionResult(
                    crop_type=vision_prediction_payload["crop_type"],
                    disease_label=vision_prediction_payload["disease_label"],
                    confidence_score=vision_prediction_payload["confidence_score"],
                    bounding_box=vision_prediction_payload.get("bounding_box"),
                )

        # 2. Invoke RAG Pipeline with Vision Metadata
        rag_response = rag_pipeline.run(
            user_query=farmer_query,
            vision_context=vision_prediction_payload,
            crop_filter=crop_override,
            disease_filter=disease_override,
            region_filter=region,
        )

        latency = time.time() - start_time

        # 3. Record metrics in MLOps Monitor
        system_monitor.record_request(
            intent=rag_response["intent"],
            latency_sec=latency,
            confidence=rag_response["retrieval_confidence"],
            needs_review=rag_response["needs_agronomist_review"],
        )

        citations_list = [
            CitationItem(
                citation_tag=c["citation_tag"],
                chunk_id=c.get("chunk_id"),
                source_doc=c.get("source_doc"),
                doc_type=c.get("doc_type"),
            )
            for c in rag_response.get("citations", [])
        ]

        return DiagnoseAndAdviseResponse(
            status="success",
            farmer_query=farmer_query,
            processed_query=rag_response["processed_query"],
            intent=rag_response["intent"],
            vision_prediction=vision_result_schema,
            answer=rag_response["answer"],
            citations=citations_list,
            retrieval_confidence=rag_response["retrieval_confidence"],
            needs_agronomist_review=rag_response["needs_agronomist_review"],
            latency_seconds=round(latency, 4),
        )

    except Exception as err:
        logger.error(f"Integration pipeline error: {err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Pipeline integration error: {str(err)}",
        )
