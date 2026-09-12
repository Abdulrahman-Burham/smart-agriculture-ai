"""Pydantic schemas for the AI Farm-Management Platform Integration API."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class VisionPredictionResult(BaseModel):
    """Result payload from the Computer Vision Disease Classifier."""
    crop_type: str = Field(..., example="potato", description="Detected crop species.")
    disease_label: str = Field(..., example="late_blight", description="Detected disease or pest label.")
    confidence_score: float = Field(..., example=0.94, description="CV model prediction confidence (0.0 to 1.0).")
    bounding_box: Optional[List[float]] = Field(None, description="Optional bounding box coordinates [x1, y1, x2, y2].")


class DiagnoseAndAdviseRequest(BaseModel):
    """Incoming request schema from Farm Management Dashboard / Farmer App."""
    farmer_query: str = Field(
        ...,
        example="عندي ندوة متاخرة في البطاطس، ايه علاجها وايه جرعة الرشاش؟",
        description="Farmer's query in Egyptian agricultural Arabic."
    )
    crop_override: Optional[str] = Field(None, example="potato", description="Optional manual crop selection.")
    disease_override: Optional[str] = Field(None, example="late_blight", description="Optional manual disease selection.")
    region: Optional[str] = Field("egypt_general", example="delta", description="Farming region in Egypt.")


class CitationItem(BaseModel):
    """Citation details backing generated agricultural advice."""
    citation_tag: str = Field(..., example="[مصدر 1]")
    chunk_id: Optional[str] = Field(None, example="chunk-12345")
    source_doc: Optional[str] = Field(None, example="late_blight_protocol.txt")
    doc_type: Optional[str] = Field(None, example="protocol")


class DiagnoseAndAdviseResponse(BaseModel):
    """Unified response payload combining Computer Vision prediction & RAG advice."""
    status: str = Field("success", example="success")
    farmer_query: str = Field(...)
    processed_query: str = Field(...)
    intent: str = Field(..., example="dosage_lookup")
    vision_prediction: Optional[VisionPredictionResult] = Field(None)
    answer: str = Field(..., description="Grounded response in Egyptian farming Arabic.")
    citations: List[CitationItem] = Field(default_factory=list)
    retrieval_confidence: float = Field(..., example=0.92)
    needs_agronomist_review: bool = Field(..., description="Flag set if confidence < threshold.")
    latency_seconds: float = Field(..., example=0.045)


class HealthCheckResponse(BaseModel):
    """System health check and readiness status."""
    status: str = Field("healthy", example="healthy")
    services: Dict[str, str] = Field(...)
    version: str = Field("1.0.0", example="1.0.0")
