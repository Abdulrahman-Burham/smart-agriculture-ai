"""Enterprise Security Headers Middleware (OWASP Top 10 Defenses).

Injects defense-in-depth HTTP security headers on all responses:
1. Content-Security-Policy (CSP): Restricts executable scripts and sources.
2. X-Frame-Options: SAMEORIGIN to prevent Clickjacking.
3. X-Content-Type-Options: nosniff to prevent MIME type sniffing attacks.
4. X-XSS-Protection: 1; mode=block.
5. Referrer-Policy: strict-origin-when-cross-origin.
6. Permissions-Policy: Restricts intrusive browser device features (camera/geo scoped to self).
7. Strict-Transport-Security (HSTS): Enforces encrypted HTTPS connections.
8. Server header obscuration: Prevents server banner fingerprinting.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Enforce OWASP security headers across all incoming requests and outgoing responses."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)

        # 1. Content Security Policy (permits necessary inline styles/scripts for charts and icons)
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self' 'unsafe-inline' 'unsafe-eval' https: data: blob:; "
            "img-src 'self' data: blob: https:; "
            "media-src 'self' data: blob: https:; "
            "font-src 'self' data: https:; "
            "connect-src 'self' https: wss:; "
            "frame-ancestors 'self';",
        )

        # 2. Clickjacking Defense
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")

        # 3. MIME-Sniffing Defense
        response.headers.setdefault("X-Content-Type-Options", "nosniff")

        # 4. XSS Filter (legacy browsers fallback)
        response.headers.setdefault("X-XSS-Protection", "1; mode=block")

        # 5. Referrer Policy
        response.headers.setdefault(
            "Referrer-Policy", "strict-origin-when-cross-origin"
        )

        # 6. Permissions Policy
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(self), microphone=(self), geolocation=(self), payment=(), usb=()",
        )

        # 7. Strict-Transport-Security (HSTS)
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
        )

        # 8. Server fingerprinting obscuration
        response.headers["Server"] = "SmartAgri-SecureGateway"

        return response
