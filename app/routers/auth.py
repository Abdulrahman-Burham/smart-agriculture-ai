"""Authentication & User Profile Router.

Handles:
- Farmer registration & password login
- Google / Microsoft / Apple social OAuth & one-tap sign in
- Persistent location (GPS / governorate) & farm preference updates
- Personal activity history retrieval
"""

from __future__ import annotations

import asyncio
import json
import urllib.parse
from urllib.parse import urlencode

import requests as ext_requests
from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from starlette.responses import FileResponse, RedirectResponse

from app.core.config import TEMPLATES_DIR
from app.core.guest_policy import load_guest_policy
from app.schemas.auth import (
    LoginPayload,
    RegisterPayload,
    SocialQuickAuthPayload,
    UserPreferencesPayload,
)
from app.services.llm_service import load_oauth_config
from app.services.weather_service import nearest_governorate
from computer_vision.storage.telemetry_repository import get_guest_usage_status
from computer_vision.storage.user_repository import (
    authenticate_user,
    get_pinned_visitor_profile,
    get_user_by_id,
    get_user_history,
    link_visitor_to_user,
    register_user,
    save_pinned_location_and_prefs,
    social_or_quick_authenticate,
)
from computer_vision.storage.utils import (
    create_auth_token,
    extract_client_info,
    extract_user_from_request,
)

router = APIRouter(prefix="", tags=["Authentication"])

_NO_CACHE_HEADERS = {
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0",
}


@router.post("/api/auth/register")
async def register_endpoint(payload: RegisterPayload, http_request: Request):
    """Register a new farmer account with Phone/Email, Password, Name, Governorate, Farm Size, and Irrigation Type."""
    client_info = extract_client_info(http_request)
    user_dict, err = await asyncio.to_thread(
        register_user,
        full_name=payload.full_name,
        identifier_raw=payload.identifier,
        password=payload.password,
        governorate=payload.governorate,
        primary_crop=payload.primary_crop,
        client_ip=client_info["client_ip"],
        device_type=client_info["device_type"],
        confirm_password=payload.confirm_password,
        farm_size_feddan=payload.farm_size_feddan,
        irrigation_type=payload.irrigation_type,
    )
    if err or not user_dict:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err or "تعذر إنشاء الحساب.")

    await asyncio.to_thread(link_visitor_to_user, client_info["visitor_hash"], user_dict)

    token = create_auth_token(user_dict)
    resp = JSONResponse(content={"status": "ok", "token": token, "user": user_dict, "visitor_id": client_info["visitor_hash"]})
    resp.set_cookie(
        key="agri_auth_token",
        value=token,
        max_age=365 * 86400,
        path="/",
        httponly=True,
        samesite="lax",
    )
    return resp


@router.post("/api/auth/login")
async def login_endpoint(payload: LoginPayload, http_request: Request):
    """Log in with Phone/Email (or Admin username) and Password."""
    client_info = extract_client_info(http_request)
    user_dict, err = await asyncio.to_thread(
        authenticate_user,
        identifier_raw=payload.identifier,
        password=payload.password,
        client_ip=client_info["client_ip"],
        device_type=client_info["device_type"],
    )
    if err or not user_dict:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=err or "بيانات الدخول غير صحيحة.")

    await asyncio.to_thread(link_visitor_to_user, client_info["visitor_hash"], user_dict)

    token = create_auth_token(user_dict)
    resp = JSONResponse(content={"status": "ok", "token": token, "user": user_dict, "visitor_id": client_info["visitor_hash"]})
    resp.set_cookie(
        key="agri_auth_token",
        value=token,
        max_age=365 * 86400,
        path="/",
        httponly=True,
        samesite="lax",
    )
    return resp


@router.get("/api/auth/oauth-config")
async def get_oauth_config_endpoint():
    """Return configured OAuth client IDs (if any) for Google/Microsoft client SDKs."""
    cfg = load_oauth_config()
    return {
        "google_client_id": cfg["google_client_id"],
        "microsoft_client_id": cfg["microsoft_client_id"],
        "is_google_configured": bool(cfg["google_client_id"]),
        "providers": ["google", "facebook", "yahoo", "microsoft", "apple", "quick_phone", "passkey"],
    }


@router.get("/api/auth/google/login")
async def google_oauth_redirect_login(request: Request, next: str = Query("/")):
    """Redirect the browser directly to the real Google OAuth 2.0 Account Chooser."""
    cfg = load_oauth_config()
    client_id = cfg.get("google_client_id", "").strip()
    client_secret = cfg.get("google_client_secret", "").strip()
    if not client_id:
        return RedirectResponse(url=f"/login?next={next}", status_code=302)

    proto = request.headers.get("x-forwarded-proto") or request.url.scheme or "https"
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or "plantapi-abdo.uaenorth.cloudapp.azure.com"
    redirect_uri = f"{proto}://{host}/api/auth/google/callback"

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code" if client_secret else "token",
        "scope": "openid email profile",
        "include_granted_scopes": "true",
        "prompt": "select_account",
        "state": next or "/",
    }
    google_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    return RedirectResponse(url=google_url, status_code=302)


@router.get("/api/auth/google/callback", include_in_schema=False)
async def google_oauth_callback_page():
    """Serve the Google OAuth 2.0 callback handler page."""
    return FileResponse(TEMPLATES_DIR / "google_callback.html", headers=_NO_CACHE_HEADERS)


@router.post("/api/auth/social")
async def social_or_quick_auth_endpoint(payload: SocialQuickAuthPayload, http_request: Request):
    """Sign in or auto-register with Google (OAuth2 code / userinfo / GSI ID Token), Microsoft, Apple, or One-Tap Phone."""
    client_info = extract_client_info(http_request)
    identifier = (payload.identifier or "").strip()
    full_name = (payload.full_name or "").strip()
    avatar_url = (payload.avatar_url or "").strip()
    provider = (payload.provider or "google").strip().lower()

    # 0. If a Google OAuth2 authorization code is provided, exchange it for access_token / id_token
    if payload.code and provider == "google":
        cfg = load_oauth_config()
        cid = cfg.get("google_client_id", "").strip()
        csec = cfg.get("google_client_secret", "").strip()
        proto = http_request.headers.get("x-forwarded-proto") or http_request.url.scheme or "https"
        host = http_request.headers.get("x-forwarded-host") or http_request.headers.get("host") or "plantapi-abdo.uaenorth.cloudapp.azure.com"
        red_uri = (payload.redirect_uri or "").strip() or f"{proto}://{host}/api/auth/google/callback"

        def _exchange_google_code(code_str: str):
            try:
                r = ext_requests.post(
                    "https://oauth2.googleapis.com/token",
                    data={
                        "code": code_str,
                        "client_id": cid,
                        "client_secret": csec,
                        "redirect_uri": red_uri,
                        "grant_type": "authorization_code",
                    },
                    timeout=8,
                )
                if r.status_code == 200:
                    return r.json()
            except Exception:
                pass
            return None

        tok_data = await asyncio.to_thread(_exchange_google_code, payload.code.strip())
        if tok_data:
            if tok_data.get("access_token"):
                payload.access_token = tok_data["access_token"]
            elif tok_data.get("id_token"):
                payload.credential_jwt = tok_data["id_token"]

    # 1. If a real Google OAuth2 access_token is provided, fetch profile from userinfo API
    if payload.access_token and provider == "google":
        def _fetch_google_userinfo(token_str: str):
            try:
                r = ext_requests.get(
                    "https://www.googleapis.com/oauth2/v3/userinfo",
                    headers={"Authorization": f"Bearer {token_str}"},
                    timeout=6,
                )
                if r.status_code == 200:
                    return r.json()
            except Exception:
                pass
            return None

        g_user = await asyncio.to_thread(_fetch_google_userinfo, payload.access_token.strip())
        if not g_user or not g_user.get("email"):
            raise HTTPException(status_code=400, detail="تعذر التحقق من رمز دخول حساب Google. يرجى المحاولة مرة أخرى.")
        identifier = g_user["email"]
        full_name = g_user.get("name") or g_user.get("given_name") or full_name
        avatar_url = g_user.get("picture") or avatar_url
        provider = "google"

    # 2. If a Google Identity Services (GSI) JWT credential is provided, verify via tokeninfo
    elif payload.credential_jwt:
        def _verify_google_jwt(jwt_str: str):
            try:
                r = ext_requests.get(
                    f"https://oauth2.googleapis.com/tokeninfo?id_token={jwt_str}",
                    timeout=6,
                )
                if r.status_code == 200:
                    return r.json()
            except Exception:
                pass
            return None

        g_info = await asyncio.to_thread(_verify_google_jwt, payload.credential_jwt.strip())
        if not g_info or not g_info.get("email"):
            raise HTTPException(status_code=400, detail="تعذر التحقق من جلسة Google. يرجى المحاولة مرة أخرى.")
        identifier = g_info["email"]
        full_name = g_info.get("name") or g_info.get("given_name") or full_name
        avatar_url = g_info.get("picture") or avatar_url
        provider = "google"

    # 3. If a Microsoft Graph access_token is provided
    elif payload.access_token and provider == "microsoft":
        def _fetch_ms_userinfo(token_str: str):
            try:
                r = ext_requests.get(
                    "https://graph.microsoft.com/v1.0/me",
                    headers={"Authorization": f"Bearer {token_str}"},
                    timeout=6,
                )
                if r.status_code == 200:
                    return r.json()
            except Exception:
                pass
            return None

        ms_user = await asyncio.to_thread(_fetch_ms_userinfo, payload.access_token.strip())
        if ms_user and (ms_user.get("mail") or ms_user.get("userPrincipalName")):
            identifier = ms_user.get("mail") or ms_user.get("userPrincipalName")
            full_name = ms_user.get("displayName") or full_name
            provider = "microsoft"

    # Inherit cookie-pinned preferences if not provided
    pinned = await asyncio.to_thread(get_pinned_visitor_profile, client_info["visitor_hash"], None)
    gov = (payload.governorate or "").strip() or pinned.get("governorate") or "القاهرة"
    crop = (payload.primary_crop or "").strip() or pinned.get("primary_crop") or ""

    user_dict, err = await asyncio.to_thread(
        social_or_quick_authenticate,
        provider=provider,
        identifier_raw=identifier,
        full_name=full_name,
        governorate=gov,
        primary_crop=crop,
        farm_size_feddan=payload.farm_size_feddan or pinned.get("farm_size_feddan") or 1.0,
        irrigation_type=payload.irrigation_type or pinned.get("irrigation_type") or "تنقيط",
        avatar_url=avatar_url,
        client_ip=client_info["client_ip"],
        device_type=client_info["device_type"],
    )
    if err or not user_dict:
        raise HTTPException(status_code=400, detail=err or "تعذر إتمام الدخول السريع.")

    await asyncio.to_thread(link_visitor_to_user, client_info["visitor_hash"], user_dict)

    token = create_auth_token(user_dict)
    resp = JSONResponse(content={
        "status": "ok",
        "token": token,
        "user": user_dict,
        "visitor_id": client_info["visitor_hash"],
        "provider": provider,
    })
    resp.set_cookie(
        key="agri_auth_token",
        value=token,
        max_age=365 * 86400,
        path="/",
        httponly=True,
        samesite="lax",
    )
    return resp


@router.post("/api/auth/logout")
async def logout_endpoint():
    """Clear authentication cookie and log out."""
    resp = JSONResponse(content={"status": "ok"})
    resp.delete_cookie("agri_auth_token", path="/")
    return resp


@router.get("/api/auth/me")
async def auth_me_endpoint(http_request: Request):
    """Return the currently authenticated user profile, linked cookie visitor profile, pinned location, and guest quota."""
    client_info = extract_client_info(http_request)
    token_user = extract_user_from_request(http_request)
    u_id = int(token_user["uid"]) if token_user and token_user.get("uid") else None
    policy = load_guest_policy()

    user_dict = None
    if u_id:
        user_dict = await asyncio.to_thread(get_user_by_id, u_id)

    if user_dict:
        await asyncio.to_thread(link_visitor_to_user, client_info["visitor_hash"], user_dict)
        pinned = await asyncio.to_thread(get_pinned_visitor_profile, client_info["visitor_hash"], u_id)
        guest_quota = await asyncio.to_thread(
            get_guest_usage_status,
            client_info["visitor_hash"],
            client_info["client_ip"],
            u_id,
            policy["max_free_uses"],
            policy["enforce_login"],
        )
        fresh_token = create_auth_token(user_dict)
        resp = JSONResponse(content={
            "authenticated": True,
            "user": user_dict,
            "token": fresh_token,
            "visitor_id": client_info["visitor_hash"],
            "pinned_profile": pinned,
            "guest_quota": guest_quota,
        })
        resp.set_cookie(
            key="agri_auth_token",
            value=fresh_token,
            max_age=365 * 86400,
            path="/",
            httponly=True,
            samesite="lax",
        )
        return resp

    pinned = await asyncio.to_thread(get_pinned_visitor_profile, client_info["visitor_hash"], None)
    guest_quota = await asyncio.to_thread(
        get_guest_usage_status,
        client_info["visitor_hash"],
        client_info["client_ip"],
        None,
        policy["max_free_uses"],
        policy["enforce_login"],
    )
    return JSONResponse(status_code=200, content={
        "authenticated": False,
        "user": None,
        "visitor_id": client_info["visitor_hash"],
        "pinned_profile": pinned,
        "guest_quota": guest_quota,
    })


@router.get("/api/user/preferences")
async def get_user_preferences_endpoint(http_request: Request):
    """Return the visitor/user's pinned location (GPS or manual governorate) and farm settings."""
    client_info = extract_client_info(http_request)
    token_user = extract_user_from_request(http_request)
    u_id = int(token_user["uid"]) if token_user and token_user.get("uid") else None
    pinned = await asyncio.to_thread(get_pinned_visitor_profile, client_info["visitor_hash"], u_id)
    return {
        "status": "ok",
        "visitor_id": client_info["visitor_hash"],
        "preferences": pinned,
    }


@router.post("/api/user/preferences")
async def save_user_preferences_endpoint(payload: UserPreferencesPayload, http_request: Request):
    """Pin the user's location (governorate + optional GPS lat/lon) and farm profile in DB and 1-year cookie."""
    client_info = extract_client_info(http_request)
    token_user = extract_user_from_request(http_request)
    u_id = int(token_user["uid"]) if token_user and token_user.get("uid") else None

    gov = payload.governorate
    lat = payload.gps_lat if payload.gps_lat is not None else payload.lat
    lon = payload.gps_lon if payload.gps_lon is not None else payload.lon

    if lat is not None and lon is not None and not gov:
        gov = nearest_governorate(float(lat), float(lon))

    saved = await asyncio.to_thread(
        save_pinned_location_and_prefs,
        visitor_id=client_info["visitor_hash"],
        user_id=u_id,
        governorate=gov,
        gps_lat=lat,
        gps_lon=lon,
        location_source=payload.location_source or ("gps" if lat is not None else "manual"),
        primary_crop=payload.primary_crop,
        farm_size_feddan=payload.farm_size_feddan,
        irrigation_type=payload.irrigation_type,
        client_ip=client_info["client_ip"],
        device_type=client_info["device_type"],
    )

    resp = JSONResponse(content={
        "status": "ok",
        "visitor_id": client_info["visitor_hash"],
        "preferences": saved,
    })
    cookie_json = urllib.parse.quote(json.dumps({
        "gov": saved.get("governorate") or "القاهرة",
        "lat": saved.get("gps_lat"),
        "lon": saved.get("gps_lon"),
        "src": saved.get("location_source") or "manual",
        "crop": saved.get("primary_crop") or "",
        "area": saved.get("farm_size_feddan") or 1.0,
        "irrig": saved.get("irrigation_type") or "تنقيط",
    }, ensure_ascii=False))
    resp.set_cookie(
        key="agri_prefs",
        value=cookie_json,
        max_age=365 * 86400,
        path="/",
        httponly=False,
        samesite="lax",
    )
    return resp


@router.get("/api/auth/my-history")
async def auth_my_history_endpoint(http_request: Request):
    """Return the logged-in farmer's personal diagnosis and chat history."""
    token_user = extract_user_from_request(http_request)
    if not token_user or not token_user.get("uid"):
        raise HTTPException(status_code=401, detail="يجب تسجيل الدخول لعرض سجلك الشخصي.")
    u_id = int(token_user["uid"])
    history = await asyncio.to_thread(get_user_history, u_id, 30)
    user_info = await asyncio.to_thread(get_user_by_id, u_id)
    return {
        "status": "ok",
        "user": user_info,
        "history": history,
    }
