"""Application Security & Authentication Dependencies.

Provides:
- Developer secret key & admin role verification (`verify_dev_key`)
- FastAPI dependencies for optional and required authenticated user sessions
"""

from __future__ import annotations

import secrets
from typing import Any, Dict, Optional

from fastapi import HTTPException, Request, status

from app.core.config import DEV_PANEL_KEY, DEV_SECRET_KEY
from computer_vision.storage.utils import extract_user_from_request


def verify_dev_key(key: str = "", request: Optional[Request] = None) -> None:
    """Validate that the caller is an authenticated Admin or provides a valid DEV_SECRET_KEY with timing-attack resistance.

    Raises HTTP 404 to avoid disclosing developer telemetry endpoints.
    """
    clean_key = (key or "").strip()
    if clean_key and any(
        secrets.compare_digest(clean_key, valid_key)
        for valid_key in (DEV_SECRET_KEY, DEV_PANEL_KEY)
    ):
        return

    if request is not None:
        auth_user = extract_user_from_request(request)
        if auth_user and auth_user.get("role") == "admin":
            return

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")


def get_current_user_optional(request: Request) -> Optional[Dict[str, Any]]:
    """FastAPI dependency: Extract the authenticated user if token present, else None."""
    return extract_user_from_request(request)


def get_current_user_required(request: Request) -> Dict[str, Any]:
    """FastAPI dependency: Require a valid authenticated user session or raise HTTP 401."""
    user = extract_user_from_request(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="يجب تسجيل الدخول للوصول إلى هذه الخدمة.",
        )
    return user
