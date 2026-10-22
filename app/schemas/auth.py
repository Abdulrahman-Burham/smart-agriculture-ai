"""Authentication & User Profile Schemas."""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class RegisterPayload(BaseModel):
    full_name: str = Field(..., description="Full legal or common name")
    identifier: str = Field(..., description="Egyptian mobile number or email")
    password: str = Field(..., description="Password (minimum 6 characters)")
    confirm_password: Optional[str] = Field(None, description="Password confirmation")
    governorate: str = Field("القاهرة", description="Egyptian governorate")
    primary_crop: str = Field("", description="Main crop cultivated")
    farm_size_feddan: float = Field(1.0, description="Farm size in feddans")
    irrigation_type: str = Field(
        "غمر", description="Irrigation method (غمر / تنقيط / رش)"
    )


class LoginPayload(BaseModel):
    identifier: str = Field(..., description="Egyptian mobile number or email")
    password: str = Field(..., description="Account password")


class SocialQuickAuthPayload(BaseModel):
    provider: str = Field(
        "google", description="google | microsoft | apple | quick_phone | passkey"
    )
    identifier: str = Field("", description="Phone number or email")
    full_name: str = Field("", description="Full name from social profile")
    governorate: str = Field("القاهرة", description="Governorate")
    primary_crop: str = Field("", description="Primary crop")
    farm_size_feddan: float = Field(1.0, description="Farm size in feddans")
    irrigation_type: str = Field("تنقيط", description="Irrigation method")
    credential_jwt: str = Field("", description="Google ID Token / Credential JWT")
    access_token: str = Field("", description="OAuth access token")
    code: Optional[str] = Field(None, description="Google OAuth authorization code")
    redirect_uri: Optional[str] = Field(None, description="OAuth redirect URI")
    avatar_url: Optional[str] = Field(None, description="User avatar image URL")


class UserPreferencesPayload(BaseModel):
    governorate: Optional[str] = Field(None, description="Preferred governorate")
    gps_lat: Optional[float] = Field(None, description="GPS latitude")
    gps_lon: Optional[float] = Field(None, description="GPS longitude")
    lat: Optional[float] = Field(None, description="GPS latitude alias")
    lon: Optional[float] = Field(None, description="GPS longitude alias")
    location_source: str = Field("manual", description="manual | gps | ip")
    primary_crop: Optional[str] = Field(None, description="Primary crop")
    farm_size_feddan: Optional[float] = Field(None, description="Farm size in feddans")
    irrigation_type: Optional[str] = Field(None, description="Irrigation method")
