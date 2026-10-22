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
    return any(
        k in ua for k in ("mobile", "android", "iphone", "ipad", "ipod", "harmonyos")
    )


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


@router.get("/offline-guide")
@router.head("/offline-guide")
async def serve_offline_guide():
    """Serve the offline field first-aid and agricultural safety guide."""
    return FileResponse(STATIC_DIR / "offline_guide.html", headers=_NO_CACHE_HEADERS)


@router.get("/epidemic-map")
@router.head("/epidemic-map")
async def serve_epidemic_map():
    """Serve the interactive Egyptian epidemic hazard & weather heatmap."""
    return FileResponse(TEMPLATES_DIR / "epidemic_map.html", headers=_NO_CACHE_HEADERS)


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


@router.get("/manifest.json")
async def serve_pwa_manifest():
    """Serve Progressive Web App manifest."""
    return FileResponse(
        STATIC_DIR / "manifest.json", media_type="application/manifest+json"
    )


@router.get("/service-worker.js")
async def serve_service_worker():
    """Serve Progressive Web App service worker script."""
    return FileResponse(
        STATIC_DIR / "service-worker.js", media_type="application/javascript"
    )


@router.get("/prescription/{image_id}")
async def serve_prescription_page(image_id: int):
    """Serve official printable agricultural treatment prescription."""
    import asyncio
    import jinja2
    from fastapi.responses import HTMLResponse
    from computer_vision.storage.image_repository import get_image_record_by_id

    record = await asyncio.to_thread(get_image_record_by_id, image_id)
    if not record:
        return HTMLResponse(
            content="""
            <!DOCTYPE html><html lang="ar" dir="rtl"><head><meta charset="utf-8">
            <title>الروشتة غير موجودة</title>
            <style>body{font-family:sans-serif;text-align:center;padding:50px;color:#333;background:#f9fafb;}a{color:#059669;font-weight:bold;text-decoration:none;}</style>
            </head><body>
            <h2>⚠️ عذراً، الروشتة المطلوبة غير متوفرة أو انتهت صلاحيتها</h2>
            <p>تأكد من رقم الروشتة وحاول الفحص مجدداً.</p>
            <br><a href="/dashboard">← العودة للمنصة الرئيسية</a>
            </body></html>
            """,
            status_code=404,
        )

    jinja_env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=jinja2.select_autoescape(["html", "xml"]),
    )
    template = jinja_env.get_template("prescription.html")
    html_content = template.render(**record, image_id=image_id)
    return HTMLResponse(content=html_content, headers=_NO_CACHE_HEADERS)
