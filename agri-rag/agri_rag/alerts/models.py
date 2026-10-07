from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class Severity(str, Enum):
    info = "info"
    warning = "warning"
    critical = "critical"


class AlertType(str, Enum):
    irrigation = "irrigation"
    fertilization = "fertilization"
    soil = "soil"
    disease = "disease"
    weather = "weather"


SEVERITY_ORDER = {Severity.critical: 0, Severity.warning: 1, Severity.info: 2}


class Alert(BaseModel):
    farm_id: str
    rule_id: str
    type: AlertType
    severity: Severity
    title: str
    message: str
    reasons: list[str] = Field(default_factory=list)  # the exact numbers/facts that triggered it
    action: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    guidance: str | None = None  # RAG-grounded elaboration (optional enrichment)
    sources: list[dict] = Field(default_factory=list)
