"""Application Pydantic Schemas Package."""

from app.schemas.auth import (
    LoginPayload,
    RegisterPayload,
    SocialQuickAuthPayload,
    UserPreferencesPayload,
)
from app.schemas.calculator import (
    SalinityRequest,
    SalinityResponse,
    TankMixRequest,
    TankMixResponse,
)
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    CitationItem,
    TTSPayload,
)
from app.schemas.dev import (
    GeminiConfigPayload,
    GeminiKeyPayload,
    GuestPolicyPayload,
    OAuthConfigPayload,
    TelegramConfigPayload,
    VerifyImagePayload,
)
from app.schemas.diagnose import (
    CVPrediction,
    DiagnoseAndAdviseRequest,
    DiagnoseAndAdviseResponse,
    DiagnoseRequest,
    DiagnoseResponse,
    FollowupEvaluationResponse,
    VisionPredictionResult,
)
from app.schemas.system import (
    HealthCheckResponse,
    HealthResponse,
)
from app.schemas.weather import AgronomicAlert, WeatherResponse

__all__ = [
    "RegisterPayload",
    "LoginPayload",
    "SocialQuickAuthPayload",
    "UserPreferencesPayload",
    "ChatRequest",
    "ChatResponse",
    "CitationItem",
    "TTSPayload",
    "DiagnoseRequest",
    "DiagnoseResponse",
    "FollowupEvaluationResponse",
    "CVPrediction",
    "VisionPredictionResult",
    "DiagnoseAndAdviseRequest",
    "DiagnoseAndAdviseResponse",
    "AgronomicAlert",
    "WeatherResponse",
    "HealthResponse",
    "HealthCheckResponse",
    "GuestPolicyPayload",
    "GeminiKeyPayload",
    "GeminiConfigPayload",
    "OAuthConfigPayload",
    "VerifyImagePayload",
    "TelegramConfigPayload",
    "TankMixRequest",
    "TankMixResponse",
    "SalinityRequest",
    "SalinityResponse",
]
