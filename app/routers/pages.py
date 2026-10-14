"""Pages Router: HTML Templates, User Interfaces, and Static Brand Assets."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request
from starlette.responses import FileResponse

from app.core.config import STATIC_DIR, TEMPLATES_DIR
from app.core.security import verify_dev_key

router = APIRouter(include_in_schema=False)

_NO_CACHE_HEADERS = {
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0",
}


def is_mobile_request(request: Request) -> bool:
    """Detect if the incoming request comes from a smartphone or tablet."""
    ua = (request.headers.get("user-agent") or "").lower()
    return any(k in ua for k in ("mobile", "android", "iphone", "ipad", "ipod", "harmonyos"))


@router.get("/")
@router.head("/")
@router.get("/landing")
@router.head("/landing")
async def serve_landing_page(request: Request):
    """Serve the official Arabic AgriTech Landing Page at root (/), or platform if ?view= is specified."""
    view_param = (request.query_params.get("view") or "").lower()
    if view_param == "desktop":
        return FileResponse(STATIC_DIR / "index.html", headers=_NO_CACHE_HEADERS)
    if view_param == "mobile":
        return FileResponse(STATIC_DIR / "mobile.html", headers=_NO_CACHE_HEADERS)
    return FileResponse(STATIC_DIR / "landing.html", headers=_NO_CACHE_HEADERS)


@router.get("/dashboard")
@router.head("/dashboard")
@router.get("/app")
@router.head("/app")
async def serve_dashboard(request: Request):
    """Serve the dedicated mobile app UI on phones or the desktop dashboard on PC."""
    if is_mobile_request(request):
        return FileResponse(STATIC_DIR / "mobile.html", headers=_NO_CACHE_HEADERS)
    return FileResponse(STATIC_DIR / "index.html", headers=_NO_CACHE_HEADERS)


@router.get("/m")
@router.head("/m")
@router.get("/mobile")
@router.head("/mobile")
async def serve_mobile_ui():
    """Serve the dedicated native-style mobile application interface."""
    return FileResponse(STATIC_DIR / "mobile.html", headers=_NO_CACHE_HEADERS)


@router.get("/simple")
@router.head("/simple")
async def serve_simple_ui():
    """Serve isolated simple 2-button image diagnosis interface."""
    return FileResponse(STATIC_DIR / "simple.html", headers=_NO_CACHE_HEADERS)


@router.get("/login")
@router.head("/login")
async def serve_login_page():
    """Serve the Arabic Login & Registration page."""
    return FileResponse(TEMPLATES_DIR / "login.html", headers=_NO_CACHE_HEADERS)


@router.get("/auth/choose-account")
@router.head("/auth/choose-account")
async def serve_oauth_chooser_page():
    """Serve the Google/Facebook/Yahoo Account Chooser tab."""
    return FileResponse(TEMPLATES_DIR / "oauth_chooser.html", headers=_NO_CACHE_HEADERS)


@router.get("/dev-panel")
async def serve_developer_dashboard(request: Request, key: str = Query("")):
    """Serve the secret developer telemetry dashboard (accessible via Admin login or ?key=DEV_SECRET_KEY)."""
    verify_dev_key(key, request)
    return FileResponse(TEMPLATES_DIR / "dev_dashboard.html")


@router.get("/favicon.ico")
async def serve_favicon():
    """Serve brand favicon."""
    return FileResponse(STATIC_DIR / "favicon.ico", media_type="image/x-icon")


@router.get("/logo.png")
async def serve_logo():
    """Serve brand logo image."""
    return FileResponse(STATIC_DIR / "logo.png", media_type="image/png")
