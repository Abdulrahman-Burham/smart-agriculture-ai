"""Silent Developer Telemetry & Traffic Observability Middleware.

Assigns persistent visitor cookies (`agri_vid`), links requests to authenticated
user profiles, calculates request latency, records error tracebacks, and logs visits.
"""

from __future__ import annotations

import asyncio
import secrets
import time
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from computer_vision.storage.telemetry_repository import (
    save_error_log,
    save_visitor_log,
)
from computer_vision.storage.utils import extract_client_info, extract_user_from_request

_IGNORE_PREFIXES = (
    "/api/dev",
    "/dev-panel",
    "/static",
    "/favicon.ico",
    "/logo.png",
    "/health",
)


class SilentTelemetryMiddleware(BaseHTTPMiddleware):
    """Starlette middleware capturing silent telemetry without impacting user response times."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_ts = time.time()
        path = request.url.path

        existing_vid = (request.cookies.get("agri_vid") or "").strip()
        is_new_vid = False
        if not existing_vid or len(existing_vid) < 6:
            existing_vid = "vid_" + secrets.token_hex(6)
            is_new_vid = True
        request.state.visitor_id = existing_vid

        client_info = extract_client_info(request)
        auth_user = extract_user_from_request(request)
        status_code = 500

        try:
            response = await call_next(request)
            status_code = response.status_code
            if is_new_vid:
                response.set_cookie(
                    key="agri_vid",
                    value=existing_vid,
                    max_age=365 * 86400,
                    path="/",
                    httponly=False,
                    samesite="lax",
                )
            return response
        except Exception as exc:
            if not path.startswith("/api/dev") and path != "/dev-panel":
                await asyncio.to_thread(
                    save_error_log,
                    endpoint=path,
                    error=exc,
                    status_code=500,
                    client_ip=client_info["client_ip"],
                    user_agent=client_info["user_agent"],
                    device_type=client_info["device_type"],
                )
            raise
        finally:
            if not any(path.startswith(p) for p in _IGNORE_PREFIXES):
                latency_ms = round((time.time() - start_ts) * 1000, 2)
                asyncio.create_task(
                    asyncio.to_thread(
                        save_visitor_log,
                        method=request.method,
                        path=path,
                        status_code=status_code,
                        latency_ms=latency_ms,
                        query_string=str(request.url.query or ""),
                        client_ip=client_info["client_ip"],
                        visitor_hash=client_info["visitor_hash"],
                        user_agent=client_info["user_agent"],
                        device_type=client_info["device_type"],
                        browser_os=client_info["browser_os"],
                        referer=client_info["referer"],
                        user_id=auth_user.get("uid") if auth_user else None,
                        user_name=auth_user.get("name", "") if auth_user else "",
                        user_identifier=auth_user.get("identifier", "")
                        if auth_user
                        else "",
                    )
                )
