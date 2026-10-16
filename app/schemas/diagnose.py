"""Computer Vision & Plant Disease Diagnosis Schemas."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.schemas.chat import CitationItem


class DiagnoseRequest(BaseModel):
    query: str = Field("", description="Optional farmer question or symptom observation accompanying the leaf image")


class CVPrediction(BaseModel):
    label: str = Field("", description="English disease class identifier")
    label_ar: str = Field("", description="Arabic disease class name")
    confidence: float = Field(0.0, description="Confidence fraction 0.0 to 1.0")


class DiagnoseResponse(BaseModel):
    is_plant: bool = Field(True, description="Whether the uploaded image is confirmed to be a plant/crop")
    rejection_reason: str = Field("", description="Explanation in Arabic if rejected as non-plant")
    cv_result: Dict[str, Any] = Field(default_factory=dict, description="Computer vision prediction details")
    advice: str = Field("", description="Agronomic treatment and prevention advice")
    sources: List[str] = Field(default_factory=list, description="Agronomic references cited")
    confidence: float = Field(0.0, description="Overall diagnostic confidence")
    latency: float = Field(0.0, description="Total pipeline latency in seconds")
    session_id: str = Field("", description="Session ID for chat follow-up")
    image_id: Optional[int] = Field(None, description="Database record ID for prescription retrieval")
    prescription_url: Optional[str] = Field(None, description="Direct URL to view/print official prescription")



class VisionPredictionResult(BaseModel):
    """Result payload from the Computer Vision Disease Classifier."""
    crop_type: str = Field(..., examples=["potato"], description="Detected crop species.")
    disease_label: str = Field(..., examples=["late_blight"], description="Detected disease or pest label.")
    confidence_score: float = Field(..., examples=[0.94], description="CV model prediction confidence (0.0 to 1.0).")
    bounding_box: Optional[List[float]] = Field(None, description="Optional bounding box coordinates [x1, y1, x2, y2].")


class DiagnoseAndAdviseRequest(BaseModel):
    """Incoming request schema from Farm Management Dashboard / Farmer App."""
    farmer_query: str = Field(
        ...,
        examples=["عندي ندوة متاخرة في البطاطس، ايه علاجها وايه جرعة الرشاش؟"],
        description="Farmer's query in Egyptian agricultural Arabic.",
    )
    crop_override: Optional[str] = Field(None, examples=["potato"], description="Optional manual crop selection.")
    disease_override: Optional[str] = Field(None, examples=["late_blight"], description="Optional manual disease selection.")
    region: Optional[str] = Field("egypt_general", examples=["delta"], description="Farming region in Egypt.")


class DiagnoseAndAdviseResponse(BaseModel):
    """Unified response payload combining Computer Vision prediction & RAG advice."""
    status: str = Field("success", examples=["success"])
    farmer_query: str = Field(...)
    processed_query: str = Field(...)
    intent: str = Field(..., examples=["dosage_lookup"])
    vision_prediction: Optional[VisionPredictionResult] = Field(None)
    answer: str = Field(..., description="Grounded response in Egyptian farming Arabic.")
    citations: List[CitationItem] = Field(default_factory=list)
    retrieval_confidence: float = Field(..., examples=[0.92])
    needs_agronomist_review: bool = Field(..., description="Flag set if confidence < threshold.")


class FollowupEvaluationResponse(BaseModel):
    status: str = "success"
    original_image_id: int = Field(..., description="ID of baseline image diagnosis")
    baseline_image_id: Optional[int] = Field(None, description="Alias for original_image_id")
    followup_image_id: int = Field(..., description="ID of new follow-up image scan")
    days_since_treatment: int = Field(7, description="Number of days elapsed since treatment")
    days_elapsed: Optional[int] = Field(None, description="Alias for days_since_treatment")
    applied_treatment: str = Field("", description="Treatment applied by farmer")
    original_disease: str = Field(..., description="Original disease diagnosed")
    baseline_disease: Optional[str] = Field(None, description="Alias for original_disease")
    current_disease: str = Field(..., description="Current disease detected in follow-up")
    followup_disease: Optional[str] = Field(None, description="Alias for current_disease")
    recovery_status: str = Field(..., description="controlled | active | healed | changed | recovering | degraded")
    recovery_status_ar: str = Field(..., description="Human-readable Arabic recovery status")
    recovery_score_percent: float = Field(..., description="Estimated recovery percentage (0 to 100)")
    recovery_score: Optional[float] = Field(None, description="Alias for recovery_score_percent")
    clinical_comparison_ar: str = Field(..., description="Visual clinical evolution analysis")
    advice: Optional[str] = Field(None, description="Alias for clinical comparison and action")
    recommended_action_ar: str = Field(..., description="Next agronomic step")
    should_repeat_spray: bool = Field(False, description="Whether another spray application is required")
    latency_seconds: float = Field(0.0, description="Latency in seconds")

