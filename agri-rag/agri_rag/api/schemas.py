from __future__ import annotations

from pydantic import BaseModel, Field

from ..alerts.models import Alert
from ..domain.farm import FarmContext


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000, description="Arabic (Egyptian dialect OK) question, or STT transcript")
    session_id: str | None = Field(None, max_length=64)
    crop: str | None = None
    farm: FarmContext | None = Field(None, description="Structured output of OCR (soil) + Vision (diagnoses) + weather")


class ChatResponse(BaseModel):
    answer: str
    grounded: bool
    session_id: str
    sources: list[dict]
    cited_ids: list[int]
    timings: dict


class AlertsRequest(BaseModel):
    farm: FarmContext
    enrich: bool = Field(False, description="Add RAG-grounded guidance to each non-info alert (adds LLM latency)")


class AlertsResponse(BaseModel):
    farm_id: str
    alerts: list[Alert]


class ReindexRequest(BaseModel):
    reset: bool = False


class ReindexResponse(BaseModel):
    documents: int
    chunks: int
    seconds: float
    sources: list[str]
