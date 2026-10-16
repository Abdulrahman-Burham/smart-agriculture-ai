"""Developer Panel, Telemetry, and Active Learning Schemas."""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class GuestPolicyPayload(BaseModel):
    enforce_login: bool = Field(True, description="Whether to require login after max_free_uses")
    max_free_uses: int = Field(3, description="Allowed free trial image scans/chats")


class GeminiKeyPayload(BaseModel):
    api_key: str = Field(..., description="Gemini API Key to add to rotation pool")


class GeminiConfigPayload(BaseModel):
    primary_model: Optional[str] = Field(None, description="Model to switch to")
    delete_key_mask: Optional[str] = Field(None, description="Masked key identifier to remove")


class OAuthConfigPayload(BaseModel):
    google_client_id: Optional[str] = Field(None, description="Google OAuth Client ID")
    microsoft_client_id: Optional[str] = Field(None, description="Microsoft OAuth Client ID")
    dev_key: Optional[str] = Field(None, description="Developer key if unauthenticated")


class VerifyImagePayload(BaseModel):
    image_id: int = Field(..., description="ID of the uploaded image to verify")
    verified_label: str = Field(..., description="Correct disease ground truth label")
    developer_notes: str = Field("", description="Optional developer comments or retraining notes")


class TelegramConfigPayload(BaseModel):
    bot_token: str = Field("", description="Telegram Bot API Token from @BotFather")
    chat_id: str = Field("", description="Telegram chat or group ID")
    enabled: bool = Field(True, description="Enable or disable real-time alerts")

