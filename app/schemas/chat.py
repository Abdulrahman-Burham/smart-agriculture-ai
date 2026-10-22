"""Chat & Agronomic Consultation Schemas."""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class CitationItem(BaseModel):
    """Citation details backing generated agricultural advice."""

    citation_tag: str = Field(..., examples=["[مصدر 1]"])
    chunk_id: Optional[str] = Field(None, examples=["chunk-12345"])
    source_doc: Optional[str] = Field(None, examples=["late_blight_protocol.txt"])
    doc_type: Optional[str] = Field(None, examples=["protocol"])


class ChatRequest(BaseModel):
    query: str = Field(
        ..., description="Farmer question in Egyptian Arabic or standard Arabic"
    )
    location: str = Field("Cairo", description="Location name or governorate")
    session_id: Optional[str] = Field(
        None, description="Conversation session ID for continuity"
    )
    crop: Optional[str] = Field(None, description="Crop filter or focus")
    rag_choice: str = Field("agri_rag", description="RAG engine selection")
    area_feddan: Optional[float] = Field(None, description="Farm area in feddans")
    irrigation_type: Optional[str] = Field(None, description="Irrigation method")
    lat: Optional[float] = Field(None, description="GPS latitude")
    lon: Optional[float] = Field(None, description="GPS longitude")


class ChatResponse(BaseModel):
    answer: str = Field(..., description="Grounded agronomic advice")
    weather: str = Field("", description="Weather context or advisory")
    sources: List[str] = Field(
        default_factory=list, description="List of cited agronomic references"
    )
    confidence: float = Field(0.0, description="Confidence score")
    latency: float = Field(0.0, description="Latency in seconds")
    intent: str = Field("", description="Detected intent")
    session_id: str = Field("", description="Session ID")
    model_used: str = Field(
        "Agri-RAG (Gemini + Hybrid e5/BM25)", description="Model designation"
    )


class TTSPayload(BaseModel):
    text: str = Field(..., description="Text to synthesize")
    voice: str = Field("ar-EG-ShakirNeural", description="Voice identifier")
    colloquial: bool = Field(
        True, description="Whether to transform to spoken Egyptian colloquial"
    )
