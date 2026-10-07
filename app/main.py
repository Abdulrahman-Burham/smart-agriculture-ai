"""Unified FastAPI Gateway: Agri-RAG + Computer Vision + Dashboard + Silent Developer Telemetry."""

from __future__ import annotations

import asyncio
import csv
import io
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests as ext_requests
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.responses import FileResponse

from computer_vision.db_storage import (
    authenticate_user,
    build_rag_finetuning_jsonl,
    build_retraining_zip,
    create_auth_token,
    extract_client_info,
    extract_user_from_request,
    get_agent_memory_context,
    get_developer_analytics,
    get_image_blob_by_id,
    get_pinned_visitor_profile,
    get_user_by_id,
    get_user_history,
    init_db,
    link_visitor_to_user,
    register_user,
    save_chat_log,
    save_error_log,
    save_image_record,
    save_pinned_location_and_prefs,
    save_visitor_log,
    update_image_ground_truth,
)
import secrets as _secrets

load_dotenv()
init_db()

logger = logging.getLogger(__name__)

AGRI_RAG_URL = os.environ.get("AGRI_RAG_URL", "http://127.0.0.1:8070")
DEV_SECRET_KEY = os.environ.get("DEV_SECRET_KEY", "abdo-dev-2026")
KNOWN_AGRI_RAG_CROPS = {"طماطم", "بطاطس", "ذرة", "قمح", "مانجو", "أرز"}

# ─── Pydantic Schemas ───────────────────────────────────────────────

class ChatRequest(BaseModel):
    query: str
    location: str = "Cairo"
    session_id: Optional[str] = None
    crop: Optional[str] = None
    rag_choice: str = "agri_rag"
    area_feddan: Optional[float] = None
    irrigation_type: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None

class ChatResponse(BaseModel):
    answer: str
    weather: str = ""
    sources: List[str] = []
    confidence: float = 0.0
    latency: float = 0.0
    intent: str = ""
    session_id: str = ""
    model_used: str = "Agri-RAG (Gemini + Hybrid e5/BM25)"

class DiagnoseRequest(BaseModel):
    query: str = ""

class CVPrediction(BaseModel):
    label: str = ""
    label_ar: str = ""
    confidence: float = 0.0

class DiagnoseResponse(BaseModel):
    cv_result: Dict[str, Any] = {}
    advice: str = ""
    sources: List[str] = []
    confidence: float = 0.0
    latency: float = 0.0
    session_id: str = ""

class WeatherResponse(BaseModel):
    temperature: Optional[float] = None
    wind_speed: Optional[float] = None
    windspeed: Optional[float] = None
    humidity: Optional[float] = None
    governorate: str = "القاهرة"
    season: str = ""
    date: str = ""
    is_gps: bool = False
    source: str = "governorate"
    lat: Optional[float] = None
    lon: Optional[float] = None

class HealthResponse(BaseModel):
    status: str = "healthy"
    services: Dict[str, str] = {}
    version: str = "2.8.0-cookies-pinned-loc"


class RegisterPayload(BaseModel):
    full_name: str
    identifier: str
    password: str
    confirm_password: Optional[str] = None
    governorate: str = "القاهرة"
    primary_crop: str = ""
    farm_size_feddan: float = 1.0
    irrigation_type: str = "غمر"


class LoginPayload(BaseModel):
    identifier: str
    password: str


class UserPrefsPayload(BaseModel):
    governorate: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    location_source: str = "manual"
    primary_crop: Optional[str] = None
    farm_size_feddan: Optional[float] = None
    irrigation_type: Optional[str] = None


# ─── Initialize FastAPI ─────────────────────────────────────────────

from fastapi.middleware.gzip import GZipMiddleware

app = FastAPI(
    title="الخبير الزراعي — Smart Agriculture AI",
    description="Production Gateway: Agri-RAG + Computer Vision + Authentication + Dashboard",
    version="2.8.0",
)

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def warmup_models_on_startup():
    """Warm up Computer Vision classifier on server startup so first user request is instant."""
    asyncio.create_task(asyncio.to_thread(get_cv_classifier))


@app.middleware("http")
async def silent_telemetry_middleware(request: Request, call_next):
    """Assign persistent visitor cookie (agri_vid), link to authenticated user, and log telemetry."""
    start_ts = time.time()
    path = request.url.path

    existing_vid = (request.cookies.get("agri_vid") or "").strip()
    is_new_vid = False
    if not existing_vid or len(existing_vid) < 6:
        existing_vid = "vid_" + _secrets.token_hex(6)
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
        # Exclude developer secret endpoints, health checks, and static asset noise
        ignore_prefixes = ("/api/dev", "/dev-panel", "/static", "/favicon.ico", "/logo.png", "/health")
        if not any(path.startswith(p) for p in ignore_prefixes):
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
                    user_identifier=auth_user.get("identifier", "") if auth_user else "",
                )
            )


# Mount static files for dashboard
app.mount("/static", StaticFiles(directory="app/static"), name="static")


# ─── Lazy Globals (initialized on first request) ────────────────────

_rag_pipeline = None
_cv_classifier = None
_local_agri_rag_container = None


def get_local_agri_rag():
    """Fallback in-process Agri-RAG container if port 8070 service is not running locally."""
    global _local_agri_rag_container
    if _local_agri_rag_container is None:
        agri_rag_dir = Path(__file__).resolve().parent.parent / "agri-rag"
        if agri_rag_dir.exists() and str(agri_rag_dir) not in sys.path:
            sys.path.insert(0, str(agri_rag_dir))
        from dotenv import dotenv_values
        env_file = agri_rag_dir / ".env"
        if env_file.exists():
            for k, v in dotenv_values(str(env_file)).items():
                if v is not None and k not in os.environ:
                    os.environ[k] = v
        from agri_rag.container import build_container
        _local_agri_rag_container = build_container()
    return _local_agri_rag_container


async def query_agri_rag(
    question: str,
    session_id: Optional[str] = None,
    crop: Optional[str] = None,
    farm: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Call Agri-RAG (/v1/chat on port 8070, or in-process container fallback)."""
    payload: Dict[str, Any] = {"question": question}
    if session_id:
        payload["session_id"] = session_id
    if crop:
        payload["crop"] = crop
    if farm:
        payload["farm"] = farm

    try:
        r = await asyncio.to_thread(
            ext_requests.post,
            f"{AGRI_RAG_URL}/v1/chat",
            json=payload,
            timeout=25,
        )
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        logger.warning(f"HTTP Agri-RAG connection notice ({e}), trying in-process agri-rag...")

    c = await asyncio.to_thread(get_local_agri_rag)
    from agri_rag.domain.farm import FarmContext
    farm_obj = FarmContext(**farm) if farm else None
    res = await c.pipeline.ask(question, session_id=session_id, farm=farm_obj, crop=crop)
    return {
        "answer": res.answer,
        "grounded": res.grounded,
        "session_id": res.session_id,
        "sources": res.sources,
        "cited_ids": res.cited_ids,
        "timings": res.timings,
    }


def format_agri_rag_sources(data: Dict[str, Any]) -> tuple[List[str], float]:
    """Extract formatted source badges and top similarity score from Agri-RAG response."""
    raw_sources = data.get("sources", []) or []
    cited_ids = set(data.get("cited_ids", []) or [])

    selected = [s for s in raw_sources if s.get("id") in cited_ids]
    if not selected:
        selected = raw_sources[:3]

    formatted: List[str] = []
    for s in selected:
        sid = s.get("id", "?")
        title = s.get("title") or s.get("source") or "مرجع زراعي"
        section = s.get("section") or ""
        label = f"[{sid}] {title}" + (f" — {section}" if section else "")
        if label not in formatted:
            formatted.append(label)

    top_sim = max(
        (float(s.get("similarity") or 0.0) for s in raw_sources),
        default=0.88 if data.get("grounded") else 0.0,
    )
    return formatted, round(top_sim, 4)


def get_rag_pipeline():
    """Lazily initialize and return the legacy RAG pipeline."""
    global _rag_pipeline
    if _rag_pipeline is None:
        from rag.pipeline import AgriculturalRAGPipeline

        logger.info("Initializing Agricultural RAG Pipeline...")
        _rag_pipeline = AgriculturalRAGPipeline(
            persist_directory="data/chroma_db",
            collection_name="agri_knowledge_base",
            embedding_model="intfloat/multilingual-e5-small",
            top_k=5,
            similarity_threshold=0.05,
        )

        pdf_path = Path("التوصيات_المعتمدة_لمكافحة_الآفات_الزراعية.pdf")
        if pdf_path.exists():
            _rag_pipeline.ingest_pdfs([str(pdf_path)])

        data_dir = Path("data/sample_knowledge_base")
        if data_dir.exists():
            docs = []
            for p in data_dir.glob("*.txt"):
                docs.append({
                    "source_doc": p.name,
                    "doc_type": "guide",
                    "crop_type": "general",
                    "disease_name": "general",
                    "region": "egypt_general",
                    "content": p.read_text(encoding="utf-8"),
                })
            if docs:
                _rag_pipeline.ingest_documents(docs)

    return _rag_pipeline


def get_cv_classifier():
    """Lazily initialize and return the CV classifier."""
    global _cv_classifier
    if _cv_classifier is None:
        try:
            from computer_vision.inference.classifier import PlantDiseaseClassifier
            _cv_classifier = PlantDiseaseClassifier()
            logger.info("✅ Plant Disease CV Model loaded.")
        except Exception as e:
            logger.warning(f"⚠️ CV Model not available: {e}")
            _cv_classifier = "unavailable"
    return _cv_classifier if _cv_classifier != "unavailable" else None


# ─── Routes ──────────────────────────────────────────────────────────

_NO_CACHE_HEADERS = {
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0",
}


_MOBILE_UA_KEYWORDS = (
    "mobile", "android", "iphone", "ipad", "ipod", "windows phone", "webos", "blackberry", "opera mini", "iemobile"
)


def _is_mobile_request(request: Request) -> bool:
    view_param = (request.query_params.get("view") or "").lower()
    if view_param == "desktop":
        return False
    if view_param == "mobile":
        return True
    ua = (request.headers.get("user-agent") or "").lower()
    return any(k in ua for k in _MOBILE_UA_KEYWORDS)


@app.get("/", include_in_schema=False)
@app.head("/", include_in_schema=False)
@app.get("/dashboard", include_in_schema=False)
@app.head("/dashboard", include_in_schema=False)
async def serve_dashboard(request: Request):
    """Serve the dedicated mobile app UI on phones or the desktop dashboard on PC."""
    if _is_mobile_request(request):
        return FileResponse("app/static/mobile.html", headers=_NO_CACHE_HEADERS)
    return FileResponse("app/static/index.html", headers=_NO_CACHE_HEADERS)


@app.get("/m", include_in_schema=False)
@app.head("/m", include_in_schema=False)
@app.get("/mobile", include_in_schema=False)
@app.head("/mobile", include_in_schema=False)
async def serve_mobile_ui():
    """Serve the dedicated native-style mobile application interface."""
    return FileResponse("app/static/mobile.html", headers=_NO_CACHE_HEADERS)


@app.get("/simple", include_in_schema=False)
@app.head("/simple", include_in_schema=False)
async def serve_simple_ui():
    """Serve isolated simple 2-button image diagnosis interface."""
    return FileResponse("app/static/simple.html", headers=_NO_CACHE_HEADERS)


@app.get("/login", include_in_schema=False)
@app.head("/login", include_in_schema=False)
async def serve_login_page():
    """Serve the Arabic Login & Registration page."""
    return FileResponse("app/templates/login.html", headers=_NO_CACHE_HEADERS)


@app.get("/favicon.ico", include_in_schema=False)
async def serve_favicon():
    """Serve brand favicon."""
    return FileResponse("app/static/favicon.ico", media_type="image/x-icon")


@app.get("/logo.png", include_in_schema=False)
async def serve_logo():
    """Serve brand logo image."""
    return FileResponse("app/static/logo.png", media_type="image/png")


# ─── Authentication & User Profile Endpoints ────────────────────────

@app.post("/api/auth/register", tags=["Authentication"])
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
        raise HTTPException(status_code=400, detail=err or "تعذر إنشاء الحساب.")

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


@app.post("/api/auth/login", tags=["Authentication"])
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
        raise HTTPException(status_code=401, detail=err or "بيانات الدخول غير صحيحة.")

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


@app.post("/api/auth/logout", tags=["Authentication"])
async def logout_endpoint():
    """Clear authentication cookie and log out."""
    resp = JSONResponse(content={"status": "ok"})
    resp.delete_cookie("agri_auth_token", path="/")
    return resp


@app.get("/api/auth/me", tags=["Authentication"])
async def auth_me_endpoint(http_request: Request):
    """Return the currently authenticated user profile, linked cookie visitor profile, and pinned location."""
    client_info = extract_client_info(http_request)
    token_user = extract_user_from_request(http_request)
    u_id = int(token_user["uid"]) if token_user and token_user.get("uid") else None

    user_dict = None
    if u_id:
        user_dict = await asyncio.to_thread(get_user_by_id, u_id)

    if user_dict:
        await asyncio.to_thread(link_visitor_to_user, client_info["visitor_hash"], user_dict)
        pinned = await asyncio.to_thread(get_pinned_visitor_profile, client_info["visitor_hash"], u_id)
        fresh_token = create_auth_token(user_dict)
        resp = JSONResponse(content={
            "authenticated": True,
            "user": user_dict,
            "token": fresh_token,
            "visitor_id": client_info["visitor_hash"],
            "pinned_profile": pinned,
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
    return JSONResponse(status_code=401, content={
        "authenticated": False,
        "visitor_id": client_info["visitor_hash"],
        "pinned_profile": pinned,
    })


@app.get("/api/user/preferences", tags=["Authentication"])
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


@app.post("/api/user/preferences", tags=["Authentication"])
async def save_user_preferences_endpoint(payload: UserPrefsPayload, http_request: Request):
    """Pin the user's location (governorate + optional GPS lat/lon) and farm profile in DB and 1-year cookie."""
    import urllib.parse
    client_info = extract_client_info(http_request)
    token_user = extract_user_from_request(http_request)
    u_id = int(token_user["uid"]) if token_user and token_user.get("uid") else None

    gov = payload.governorate
    if payload.lat is not None and payload.lon is not None and not gov:
        gov = _nearest_governorate(float(payload.lat), float(payload.lon))

    saved = await asyncio.to_thread(
        save_pinned_location_and_prefs,
        visitor_id=client_info["visitor_hash"],
        user_id=u_id,
        governorate=gov,
        gps_lat=payload.lat,
        gps_lon=payload.lon,
        location_source=payload.location_source or ("gps" if payload.lat is not None else "manual"),
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


@app.get("/api/auth/my-history", tags=["Authentication"])
async def auth_my_history_endpoint(http_request: Request):
    """Return the logged-in farmer's personal diagnosis and chat history."""
    token_user = extract_user_from_request(http_request)
    if not token_user or not token_user.get("uid"):
        raise HTTPException(status_code=401, detail="يرجى تسجيل الدخول أولاً.")

    history = await asyncio.to_thread(get_user_history, int(token_user["uid"]), 20)
    return history


@app.get("/health", response_model=HealthResponse, tags=["System"])
@app.head("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """System health and readiness probe."""
    cv = get_cv_classifier()
    return HealthResponse(
        status="healthy",
        services={
            "api_gateway": "online",
            "agri_rag": "online",
            "cv_model": "online" if cv else "offline",
            "vector_store": "chroma_hybrid_e5_bm25",
        },
    )


_WEATHER_CACHE: Dict[str, tuple[float, WeatherResponse]] = {}
EGYPT_GOV_COORDS: Dict[str, tuple[float, float]] = {
    "القاهرة": (30.0444, 31.2357),
    "الجيزة": (30.0131, 31.2089),
    "الإسكندرية": (31.2001, 29.9187),
    "البحيرة": (31.0409, 30.4700),
    "كفر الشيخ": (31.1107, 30.9388),
    "الدقهلية": (31.0409, 31.3785),
    "الشرقية": (30.5877, 31.5020),
    "المنوفية": (30.5972, 30.9876),
    "الغربية": (30.7865, 31.0004),
    "القليوبية": (30.4660, 31.1848),
    "الإسماعيلية": (30.5965, 32.2715),
    "دمياط": (31.4175, 31.8144),
    "بورسعيد": (31.2653, 32.3019),
    "السويس": (29.9668, 32.5498),
    "الفيوم": (29.3084, 30.8428),
    "بني سويف": (29.0661, 31.0994),
    "المنيا": (28.1099, 30.7503),
    "أسيوط": (27.1810, 31.1837),
    "سوهاج": (26.5591, 31.6957),
    "قنا": (26.1551, 32.7160),
    "الأقصر": (25.6872, 32.6396),
    "أسوان": (24.0889, 32.8998),
    "مطروح": (31.3543, 27.2373),
    "الوادي الجديد": (25.4514, 30.5463),
    "البحر الأحمر": (27.2579, 33.8116),
    "شمال سيناء": (31.1321, 33.8033),
    "جنوب سيناء": (28.2417, 33.6222),
}


def _nearest_governorate(lat: float, lon: float) -> str:
    """Find the closest Egyptian governorate to the given GPS (lat, lon) coordinates."""
    import math
    best_gov = "القاهرة"
    best_dist = float("inf")
    for gov, (glat, glon) in EGYPT_GOV_COORDS.items():
        d = math.hypot(lat - glat, (lon - glon) * math.cos(math.radians(lat)))
        if d < best_dist:
            best_dist = d
            best_gov = gov
    return best_gov


_IRRIG_TO_ENUM = {
    "تنقيط": "drip",
    "drip": "drip",
    "غمر": "surface",
    "surface": "surface",
    "رش": "sprinkler",
    "sprinkler": "sprinkler",
}


@app.get("/api/weather", response_model=WeatherResponse, tags=["Tools"])
async def get_weather_endpoint(
    http_request: Request,
    governorate: Optional[str] = Query(None),
    gov: Optional[str] = Query(None),
    lat: Optional[float] = Query(None),
    lon: Optional[float] = Query(None),
    pin: bool = Query(True),
):
    """Get current weather and agricultural season by GPS, manual governorate, or the user's cookie-pinned location."""
    import datetime
    now_ts = time.time()
    client_info = extract_client_info(http_request)
    token_user = extract_user_from_request(http_request)
    u_id = int(token_user["uid"]) if token_user and token_user.get("uid") else None

    explicit_gov = (gov or governorate or "").strip()
    is_gps = lat is not None and lon is not None and (-90 <= lat <= 90) and (-180 <= lon <= 180)
    loc_source = "manual"

    if is_gps:
        gov_key = _nearest_governorate(float(lat), float(lon))
        q_lat, q_lon = round(float(lat), 4), round(float(lon), 4)
        cache_key = f"gps:{q_lat:.2f},{q_lon:.2f}"
        loc_source = "gps"
        if pin:
            await asyncio.to_thread(
                save_pinned_location_and_prefs,
                visitor_id=client_info["visitor_hash"],
                user_id=u_id,
                governorate=gov_key,
                gps_lat=q_lat,
                gps_lon=q_lon,
                location_source="gps",
                client_ip=client_info["client_ip"],
                device_type=client_info["device_type"],
            )
    elif explicit_gov:
        gov_key = explicit_gov
        q_lat, q_lon = EGYPT_GOV_COORDS.get(gov_key, (30.0444, 31.2357))
        cache_key = f"gov:{gov_key}"
        loc_source = "manual"
        if pin:
            await asyncio.to_thread(
                save_pinned_location_and_prefs,
                visitor_id=client_info["visitor_hash"],
                user_id=u_id,
                governorate=gov_key,
                location_source="manual",
                client_ip=client_info["client_ip"],
                device_type=client_info["device_type"],
            )
    else:
        # Restore from cookie/DB pinned location so IP never overrides the farmer's real governorate
        pinned = await asyncio.to_thread(get_pinned_visitor_profile, client_info["visitor_hash"], u_id)
        if pinned.get("gps_lat") is not None and pinned.get("gps_lon") is not None:
            q_lat, q_lon = round(float(pinned["gps_lat"]), 4), round(float(pinned["gps_lon"]), 4)
            gov_key = pinned.get("governorate") or _nearest_governorate(q_lat, q_lon)
            is_gps = True
            loc_source = pinned.get("location_source") or "gps"
            cache_key = f"gps:{q_lat:.2f},{q_lon:.2f}"
        else:
            gov_key = pinned.get("governorate") or "القاهرة"
            q_lat, q_lon = EGYPT_GOV_COORDS.get(gov_key, (30.0444, 31.2357))
            loc_source = pinned.get("location_source") or "pinned"
            cache_key = f"gov:{gov_key}"

    cached = _WEATHER_CACHE.get(cache_key)
    if cached and (now_ts - cached[0]) < 900:
        return cached[1]

    from rag.tools import get_current_date_context

    def _fetch():
        try:
            url = f"https://api.open-meteo.com/v1/forecast?latitude={q_lat}&longitude={q_lon}&current=temperature_2m,relative_humidity_2m,wind_speed_10m"
            r = ext_requests.get(url, timeout=4)
            if r.status_code == 200:
                cur = r.json().get("current", {})
                return cur.get("temperature_2m", 28.0), cur.get("wind_speed_10m", 12.0), cur.get("relative_humidity_2m", 50.0)
        except Exception:
            pass
        return 28.0, 12.0, 50.0

    temp, wind, hum = await asyncio.to_thread(_fetch)
    date_ctx = await asyncio.to_thread(get_current_date_context)

    resp = WeatherResponse(
        temperature=temp,
        wind_speed=wind,
        windspeed=wind,
        humidity=hum,
        governorate=gov_key,
        season=date_ctx.split("فصل ")[-1].rstrip(".") if "فصل" in date_ctx else "",
        date=datetime.datetime.now().strftime("%Y-%m-%d"),
        is_gps=is_gps,
        lat=q_lat,
        lon=q_lon,
        source=loc_source,
    )
    _WEATHER_CACHE[cache_key] = (now_ts, resp)
    return resp


@app.get("/api/chat/memory", tags=["RAG"])
async def get_chat_memory_endpoint(
    http_request: Request,
    session_id: str = Query(""),
    limit: int = Query(15, ge=1, le=50),
):
    """Return persistent conversation turns and recent leaf diagnoses for the active session/user."""
    client_info = extract_client_info(http_request)
    auth_user = extract_user_from_request(http_request)
    u_id = int(auth_user["uid"]) if auth_user and auth_user.get("uid") else None
    mem = await asyncio.to_thread(
        get_agent_memory_context,
        session_id=session_id,
        user_id=u_id,
        visitor_hash=client_info["visitor_hash"],
        max_turns=limit,
    )
    return {"status": "ok", "memory": mem}


@app.post("/api/chat", response_model=ChatResponse, tags=["RAG"])
async def chat_endpoint(request: ChatRequest, http_request: Request):
    """Agri-RAG powered agricultural Q&A chat endpoint with persistent multi-turn memory and silent developer logging."""
    start_time = time.time()
    client_info = extract_client_info(http_request)
    auth_user = extract_user_from_request(http_request)
    u_id = int(auth_user["uid"]) if auth_user and auth_user.get("uid") else None
    u_name = auth_user.get("name", "") if auth_user else ""
    u_ident = auth_user.get("identifier", "") if auth_user else ""

    # Load persistent memory (previous chat turns, recent image diagnoses, and farmer profile)
    mem_ctx = await asyncio.to_thread(
        get_agent_memory_context,
        session_id=request.session_id or "",
        user_id=u_id,
        visitor_hash=client_info["visitor_hash"],
        max_turns=15,
    )

    try:
        # Optional secondary legacy RAG branch (only if explicitly selected)
        if request.rag_choice == "legacy_rag":
            pipeline = get_rag_pipeline()
            from rag.tools import get_weather, get_current_date_context
            date_context = await asyncio.to_thread(get_current_date_context)
            weather_data = await asyncio.to_thread(get_weather)
            weather_str = ""
            if weather_data.get("status") == "success":
                weather_str = f"درجة الحرارة: {weather_data.get('temperature')}°C، سرعة الرياح: {weather_data.get('wind_speed')} كم/س."
            mem_str = f"\n[ذاكرة المحادثة والتشخيصات السابقة للمزارع:\n{mem_ctx.get('memory_notes', '')}]" if mem_ctx.get("memory_notes") else ""
            enriched_query = f"{request.query}\n(معلومة للمساعد: {date_context} {weather_str}{mem_str})"
            result = await asyncio.to_thread(pipeline.run, enriched_query)
            sources = list(set(
                f"صفحة {c.get('metadata', {}).get('page_start', '?')}"
                for c in result.get("sources", [])
            ))
            latency = round(time.time() - start_time, 3)
            conf = round(result.get("retrieval_confidence", 0), 4)

            asyncio.create_task(
                asyncio.to_thread(
                    save_chat_log,
                    user_query=request.query,
                    bot_answer=result["answer"],
                    sources=sources,
                    confidence=conf,
                    latency_ms=round(latency * 1000, 2),
                    session_id=request.session_id or "",
                    location=request.location,
                    crop=request.crop or "",
                    rag_engine="Legacy RAG",
                    client_ip=client_info["client_ip"],
                    user_agent=client_info["user_agent"],
                    device_type=client_info["device_type"],
                    visitor_hash=client_info["visitor_hash"],
                    status="success",
                    user_id=u_id,
                    user_name=u_name,
                    user_identifier=u_ident,
                )
            )

            return ChatResponse(
                answer=result["answer"],
                weather=weather_str,
                sources=sources,
                confidence=conf,
                latency=latency,
                intent=result.get("intent", ""),
                session_id=request.session_id or "",
                model_used="Legacy RAG",
            )

        # Primary Default Engine: Agri-RAG (agri-rag/ package with ChromaDB + e5 + BM25 + Gemini + Persistent Memory)
        active_crop = request.crop or mem_ctx.get("primary_crop") or ""
        area_val = request.area_feddan or mem_ctx.get("farm_size_feddan")
        raw_irrig = request.irrigation_type or mem_ctx.get("irrigation_type") or ""
        irrig_enum = _IRRIG_TO_ENUM.get(raw_irrig.strip())

        farm_ctx: Dict[str, Any] = {
            "farm_id": f"user-{u_id}" if u_id else f"visitor-{client_info['visitor_hash'][:8]}",
            "farmer_name": u_name or mem_ctx.get("farmer_name") or None,
            "governorate": request.location or mem_ctx.get("governorate") or "القاهرة",
        }
        if active_crop:
            farm_ctx["crop"] = active_crop
        if area_val and float(area_val) > 0:
            farm_ctx["area_feddan"] = float(area_val)
        if irrig_enum:
            farm_ctx["irrigation_method"] = irrig_enum
        if request.lat is not None and request.lon is not None:
            farm_ctx["latitude"] = float(request.lat)
            farm_ctx["longitude"] = float(request.lon)
        if mem_ctx.get("diagnoses"):
            farm_ctx["diagnoses"] = mem_ctx["diagnoses"]
        if mem_ctx.get("memory_notes"):
            farm_ctx["memory_notes"] = mem_ctx["memory_notes"]

        agri_data = await query_agri_rag(
            question=request.query,
            session_id=request.session_id,
            crop=active_crop if active_crop in KNOWN_AGRI_RAG_CROPS else None,
            farm=farm_ctx,
        )

        sources, top_conf = format_agri_rag_sources(agri_data)
        latency = round(time.time() - start_time, 3)
        answer_text = agri_data.get("answer", "")
        sess_id = agri_data.get("session_id", "")

        asyncio.create_task(
            asyncio.to_thread(
                save_chat_log,
                user_query=request.query,
                bot_answer=answer_text,
                sources=sources,
                confidence=top_conf,
                latency_ms=round(latency * 1000, 2),
                session_id=sess_id,
                location=request.location,
                crop=request.crop or "",
                rag_engine="Agri-RAG (e5 + BM25 + Gemini)",
                client_ip=client_info["client_ip"],
                user_agent=client_info["user_agent"],
                device_type=client_info["device_type"],
                visitor_hash=client_info["visitor_hash"],
                status="success",
                user_id=u_id,
                user_name=u_name,
                user_identifier=u_ident,
            )
        )

        return ChatResponse(
            answer=answer_text,
            weather="",
            sources=sources,
            confidence=top_conf,
            latency=latency,
            intent="agri_rag",
            session_id=sess_id,
            model_used="Agri-RAG (e5 + BM25 + Gemini)",
        )
    except Exception as e:
        latency_ms = round((time.time() - start_time) * 1000, 2)
        logger.error(f"Chat error: {e}")
        await asyncio.to_thread(
            save_chat_log,
            user_query=request.query,
            bot_answer="",
            latency_ms=latency_ms,
            session_id=request.session_id or "",
            location=request.location,
            crop=request.crop or "",
            rag_engine=request.rag_choice,
            client_ip=client_info["client_ip"],
            user_agent=client_info["user_agent"],
            device_type=client_info["device_type"],
            visitor_hash=client_info["visitor_hash"],
            status="error",
            error_message=str(e),
            user_id=u_id,
            user_name=u_name,
            user_identifier=u_ident,
        )
        await asyncio.to_thread(
            save_error_log,
            endpoint="/api/chat",
            error=e,
            status_code=500,
            client_ip=client_info["client_ip"],
            user_agent=client_info["user_agent"],
            device_type=client_info["device_type"],
            request_summary=f"query={request.query[:200]}",
        )
        raise HTTPException(status_code=500, detail=str(e))


MAX_UPLOAD_BYTES = 15 * 1024 * 1024  # 15 MB


@app.post("/api/diagnose", response_model=DiagnoseResponse, tags=["Vision + RAG"])
async def diagnose_endpoint(
    http_request: Request,
    image: UploadFile = File(...),
    query: str = Form("ما هو التشخيص وما هي خطوات العلاج والمكافحة الموصى بها؟"),
    model_choice: str = Form("EfficientNetV2B2"),
    rag_choice: str = Form("agri_rag"),
    location: str = Form("القاهرة"),
    session_id: Optional[str] = Form(None),
    area_feddan: Optional[float] = Form(None),
    irrigation_type: Optional[str] = Form(None),
):
    """Upload a leaf image → CV diagnosis + Agri-RAG grounded treatment advice + Private DB Save."""
    start_time = time.time()
    client_info = extract_client_info(http_request)
    auth_user = extract_user_from_request(http_request)
    u_id = auth_user.get("uid") if auth_user else None
    u_name = auth_user.get("name", "") if auth_user else ""
    u_ident = auth_user.get("identifier", "") if auth_user else ""

    try:
        # Step 1: Read and validate image bytes
        image_bytes = await image.read()
        if not image_bytes:
            raise HTTPException(status_code=400, detail="Empty image file.")
        if len(image_bytes) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="حجم الصورة يتجاوز الحد المسموح به (15 ميجابايت).")

        # Step 2: Run Computer Vision prediction in thread pool
        cv = get_cv_classifier()
        cv_result = {}

        if cv:
            image_stream = io.BytesIO(image_bytes)
            prediction = await asyncio.to_thread(
                cv.predict, image_stream, 3, model_choice
            )
            cv_result = prediction

        # Step 3: Build FarmContext with VisionDiagnosis + Memory and query Agri-RAG
        crop_ar = cv_result.get("crop_type_ar", "")
        predicted_ar = cv_result.get("predicted_class_ar", "")
        predicted_en = cv_result.get("predicted_class", "")
        conf_score = float(cv_result.get("top_confidence", 0.9))
        returned_session_id = session_id or ""

        memory_ctx: Dict[str, Any] = {}
        try:
            memory_ctx = await asyncio.to_thread(
                get_agent_memory_context,
                session_id=session_id or "",
                user_id=u_id,
                visitor_hash=client_info["visitor_hash"],
                max_turns=10,
            )
        except Exception as mem_err:
            logger.warning(f"Memory fetch notice in diagnose: {mem_err}")

        farmer_display_name = u_name or memory_ctx.get("farmer_name", "")
        memory_notes = memory_ctx.get("memory_notes", "")

        if rag_choice == "legacy_rag":
            pipeline = get_rag_pipeline()
            vision_context = {
                "crop_type": cv_result.get("crop_type", ""),
                "disease_label": cv_result.get("disease_name", ""),
                "confidence_score": conf_score,
            }
            enriched_query = f"{query}\n(نتيجة تحليل الصورة: المحصول: {crop_ar}، المرض المكتشف: {predicted_ar}، الثقة: {conf_score:.0%})"
            if memory_notes:
                enriched_query = f"{memory_notes}\n\n{enriched_query}"
            rag_result = await asyncio.to_thread(
                pipeline.run,
                user_query=enriched_query,
                vision_context=vision_context,
            )
            advice_text = rag_result["answer"]
            sources = list(set(
                f"صفحة {c.get('metadata', {}).get('page_start', '?')}"
                for c in rag_result.get("sources", [])
            ))
            rag_conf = round(rag_result.get("retrieval_confidence", 0), 4)
        else:
            # Primary Agri-RAG integration using FarmContext + VisionDiagnosis + Memory contract
            resolved_area = area_feddan or memory_ctx.get("area_feddan")
            raw_irrig = (irrigation_type or memory_ctx.get("irrigation_type") or "").strip()
            irrig_map = {"تنقيط": "drip", "غمر": "surface", "رش": "sprinkler", "محوري": "pivot", "drip": "drip", "surface": "surface", "sprinkler": "sprinkler"}
            resolved_irrig = irrig_map.get(raw_irrig)

            farm_payload: Dict[str, Any] = {
                "farm_id": f"user-{u_id}" if u_id else f"visitor-{client_info['visitor_hash'][:8]}",
                "farmer_name": farmer_display_name or None,
                "governorate": location or memory_ctx.get("governorate") or "القاهرة",
                "crop": crop_ar if crop_ar else (memory_ctx.get("crop") or None),
                "area_feddan": float(resolved_area) if resolved_area else None,
                "irrigation_method": resolved_irrig,
                "diagnoses": [
                    {
                        "label": f"{predicted_ar} ({predicted_en})" if predicted_ar else predicted_en,
                        "confidence": round(min(1.0, max(0.0, conf_score)), 4),
                        "crop": crop_ar if crop_ar else None,
                    }
                ],
                "memory_notes": memory_notes or None,
            }
            rag_question = (
                f"تم فحص صورة ورقة نبات {crop_ar} وكانت نتيجة التشخيص: {predicted_ar} ({predicted_en}). "
                f"ما هي الأعراض وخطوات الوقاية والمكافحة المعتمدة لهذا التشخيص في {crop_ar}؟ ({query})"
            )
            filter_crop = crop_ar if crop_ar in KNOWN_AGRI_RAG_CROPS else None

            agri_data = await query_agri_rag(
                question=rag_question,
                session_id=session_id,
                crop=filter_crop,
                farm=farm_payload,
            )
            advice_text = agri_data.get("answer", "")
            returned_session_id = agri_data.get("session_id", "") or returned_session_id
            sources, rag_conf = format_agri_rag_sources(agri_data)

        latency = round(time.time() - start_time, 3)

        # Step 4: Silently save uploaded image + diagnosis + advice + visitor info to private server Database
        try:
            await asyncio.to_thread(
                save_image_record,
                image_bytes=image_bytes,
                filename=image.filename or "leaf.jpg",
                content_type=image.content_type or "image/jpeg",
                source_endpoint="/api/diagnose",
                model_used=cv_result.get("model_used", model_choice),
                predicted_class=predicted_en,
                predicted_class_ar=predicted_ar,
                confidence=cv_result.get("confidence_str", "0.00%"),
                top_predictions=cv_result.get("top_predictions", []),
                user_query=query,
                rag_advice=advice_text,
                client_ip=client_info["client_ip"],
                user_agent=client_info["user_agent"],
                device_type=client_info["device_type"],
                visitor_hash=client_info["visitor_hash"],
                latency_ms=round(latency * 1000, 2),
                weather_snapshot=location or "القاهرة",
                user_id=u_id,
                user_name=u_name,
                user_identifier=u_ident,
            )
        except Exception as db_err:
            logger.warning(f"Database save warning: {db_err}")

        return DiagnoseResponse(
            cv_result=cv_result,
            advice=advice_text,
            sources=sources,
            confidence=rag_conf,
            latency=latency,
            session_id=returned_session_id,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Diagnose error: {e}")
        await asyncio.to_thread(
            save_error_log,
            endpoint="/api/diagnose",
            error=e,
            status_code=500,
            client_ip=client_info["client_ip"],
            user_agent=client_info["user_agent"],
            device_type=client_info["device_type"],
            request_summary=f"filename={getattr(image, 'filename', '')}, model={model_choice}",
        )
        raise HTTPException(status_code=500, detail=str(e))


# ─── Egyptian Dialect STT (Speech-to-Text) & TTS (Text-to-Speech) ───

EGYPTIAN_STT_PROMPT = (
    "أنت نظام تفريغ صوتي (Speech-to-Text) متخصص في اللهجة المصرية العامية الفلاحي والمصطلحات الزراعية المصرية.\n"
    "استمع للتسجيل الصوتي واكتب الكلام باللهجة المصرية العامية كما نطقه المتحدث بالضبط (مثل: إيه، عايز، عندي، "
    "الورق، مبقع، مسفر، أرش إيه، بكام، إمتى، ليه، إزاي، دلوقتي، عشان، يا بشمهندس).\n"
    "صحح المصطلحات الزراعية المصرية مثل: (ندوة متأخرة، ندوة مبكرة، بياض دقيقي، بياض زغبي، تريبس، أكاروس، "
    "عنكبوت أحمر، دودة ورق القطن، توتا أبسولوتا، حفار، عفن هبابي، لفحة، ذبول، موزاييك، فدان، قيراط، طماطم، "
    "بطاطس، قمح، ذرة، مانجو، عنب، خوخ، فراولة).\n"
    "أخرج النص المصري المفرغ فقط في سطر واحد بدون أي شرح أو مقدمات أو علامات تنصيص."
)

_EGYPTIAN_REPLACEMENTS = [
    ("ما هو ", "إيه هو "),
    ("ما هي ", "إيه هي "),
    ("ماذا أفعل", "أعمل إيه"),
    ("ماذا ", "إيه "),
    ("كيف يمكنني", "إزاي أقدر"),
    ("كيف ", "إزاي "),
    ("لماذا ", "ليه "),
    ("متى ", "إمتى "),
    ("أريد ", "عايز "),
    ("اريد ", "عايز "),
    ("الآن", "دلوقتي"),
    ("هكذا", "كده"),
    ("هذا ", "ده "),
    ("هذه ", "دي "),
    ("تربس", "تريبس"),
    ("اكاروس", "أكاروس"),
    ("توته ابسولوتا", "توتا أبسولوتا"),
    ("الندوه", "الندوة"),
    ("اللفحه", "اللفحة"),
]


def normalize_to_egyptian_dialect(text: str) -> str:
    """Normalize transcribed speech into natural Egyptian agricultural dialect."""
    if not text:
        return ""
    out = text.strip().strip('"\'«»')
    for src, dst in _EGYPTIAN_REPLACEMENTS:
        out = out.replace(src, dst)
    return out.strip()


_GEMINI_KEYS_FILE = Path(__file__).resolve().parent.parent / "data" / "gemini_keys.json"
_STT_KEY_RR_IDX = 0


def _get_gemini_key_pool_and_model() -> tuple[List[str], str]:
    """Return all configured Gemini API keys (env + .env + data/gemini_keys.json) and primary model."""
    keys: List[str] = []
    model_name = os.environ.get("AGRI_LLM_MODEL", "gemini-2.5-flash")

    for raw in [
        os.environ.get("AGRI_LLM_API_KEY", ""),
        os.environ.get("AGRI_LLM_API_KEYS", ""),
        os.environ.get("GEMINI_API_KEYS", ""),
        os.environ.get("GEMINI_API_KEY", ""),
        os.environ.get("GEMINI_API_KEY_2", ""),
        os.environ.get("GEMINI_API_KEY_3", ""),
        os.environ.get("GOOGLE_API_KEY", ""),
    ]:
        for part in str(raw).split(","):
            k = part.strip()
            if k and k not in keys:
                keys.append(k)

    from dotenv import dotenv_values
    for candidate in [
        Path("/home/azureuser/agri-rag-standalone/.env"),
        Path(__file__).resolve().parent.parent / "agri-rag" / ".env",
        Path(".env"),
    ]:
        try:
            if candidate.exists():
                vals = dotenv_values(str(candidate))
                for env_k in ("AGRI_LLM_API_KEY", "AGRI_LLM_API_KEYS", "GEMINI_API_KEY", "GEMINI_API_KEYS"):
                    for part in str(vals.get(env_k) or "").split(","):
                        k = part.strip()
                        if k and k not in keys:
                            keys.append(k)
                if vals.get("AGRI_LLM_MODEL"):
                    model_name = str(vals["AGRI_LLM_MODEL"])
        except Exception:
            pass

    try:
        if _GEMINI_KEYS_FILE.exists():
            saved = json.loads(_GEMINI_KEYS_FILE.read_text(encoding="utf-8"))
            for k in saved.get("keys", []):
                ks = str(k).strip()
                if ks and ks not in keys:
                    keys.append(ks)
    except Exception:
        pass

    return keys, model_name


def _get_gemini_api_key_and_model() -> tuple[str, str]:
    keys, model_name = _get_gemini_key_pool_and_model()
    return (keys[0] if keys else ""), model_name


@app.post("/api/stt", tags=["Speech (Egyptian Dialect)"])
async def egyptian_stt_endpoint(
    audio: Optional[UploadFile] = File(None),
    fallback_text: str = Form(""),
):
    """Transcribe spoken Egyptian Arabic audio into Egyptian agricultural dialect text with multi-key rotation."""
    global _STT_KEY_RR_IDX
    import base64

    if audio is not None:
        audio_bytes = await audio.read()
        if audio_bytes and len(audio_bytes) > 200:
            keys, cfg_model = _get_gemini_key_pool_and_model()
            if keys:
                n_keys = len(keys)
                start_idx = _STT_KEY_RR_IDX % n_keys
                _STT_KEY_RR_IDX += 1
                ordered_keys = [keys[(start_idx + i) % n_keys] for i in range(n_keys)]

                mime_type = (audio.content_type or "audio/webm").split(";")[0].strip().lower()
                if mime_type in ("audio/x-m4a", "audio/m4a", "audio/aac"):
                    mime_type = "audio/mp4"
                elif mime_type not in ("audio/webm", "audio/mp4", "audio/ogg", "audio/wav", "audio/mpeg", "audio/mp3"):
                    mime_type = "audio/webm"
                b64_audio = base64.b64encode(audio_bytes).decode("ascii")

                def _call_gemini_stt() -> str:
                    models = []
                    for m in [cfg_model, "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]:
                        if m and m not in models:
                            models.append(m)
                    for api_key in ordered_keys:
                        for m in models:
                            try:
                                url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={api_key}"
                                payload = {
                                    "contents": [
                                        {
                                            "parts": [
                                                {"text": EGYPTIAN_STT_PROMPT},
                                                {"inlineData": {"mimeType": mime_type, "data": b64_audio}},
                                            ]
                                        }
                                    ],
                                    "generationConfig": {"temperature": 0.1, "maxOutputTokens": 250},
                                }
                                r = ext_requests.post(url, json=payload, timeout=15)
                                if r.status_code == 200:
                                    candidates = r.json().get("candidates", [])
                                    if candidates:
                                        parts = candidates[0].get("content", {}).get("parts", [])
                                        if parts and parts[0].get("text"):
                                            return parts[0]["text"].strip()
                            except Exception as e:
                                logger.warning(f"Gemini STT model {m} notice: {e}")
                    return ""

                transcribed = await asyncio.to_thread(_call_gemini_stt)
                if transcribed:
                    return {
                        "text": normalize_to_egyptian_dialect(transcribed),
                        "dialect": "ar-EG",
                        "engine": "Gemini Egyptian Dialect STT",
                    }

    # Fallback: normalize browser ar-EG speech recognition text to Egyptian dialect
    cleaned = normalize_to_egyptian_dialect(fallback_text)
    return {
        "text": cleaned,
        "dialect": "ar-EG",
        "engine": "WebSpeech ar-EG + Egyptian Dialect Normalizer",
    }


@app.get("/api/tts", tags=["Speech (Egyptian Dialect)"])
async def egyptian_tts_endpoint(
    text: str = Query(..., description="النص المراد نطقه باللهجة المصرية"),
    voice: str = Query("ar-EG-ShakirNeural", description="ar-EG-ShakirNeural أو ar-EG-SalmaNeural"),
):
    """Synthesize natural Egyptian Arabic speech (MP3) using Microsoft Neural Egyptian voices."""
    import re
    clean_text = re.sub(r"\[\d+\]", "", text or "")
    clean_text = re.sub(r"[*#_`~>]", "", clean_text).strip()
    if not clean_text:
        raise HTTPException(status_code=400, detail="Empty text")

    selected_voice = voice if voice in ("ar-EG-ShakirNeural", "ar-EG-SalmaNeural") else "ar-EG-ShakirNeural"
    try:
        import edge_tts
        communicate = edge_tts.Communicate(clean_text[:1500], selected_voice, rate="+2%")
        audio_chunks = bytearray()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_chunks.extend(chunk["data"])
        if audio_chunks:
            return Response(content=bytes(audio_chunks), media_type="audio/mpeg")
    except Exception as e:
        logger.warning(f"Edge TTS notice: {e}")

    raise HTTPException(status_code=503, detail="TTS service fallback")


# ─── Camouflaged Developer-Only Telemetry Endpoints (Hidden from Schema & Returns 404 without Key) ───

def _verify_dev_key(key: str, request: Optional[Request] = None) -> None:
    """Return 404 Not Found unless valid DEV_SECRET_KEY or authenticated Admin session is present."""
    if key and key == DEV_SECRET_KEY:
        return
    if request is not None:
        auth_user = extract_user_from_request(request)
        if auth_user and auth_user.get("role") == "admin":
            return
    raise HTTPException(status_code=404, detail="Not Found")


@app.get("/dev-panel", include_in_schema=False)
async def serve_developer_dashboard(request: Request, key: str = Query("")):
    """Serve the secret developer telemetry dashboard (accessible via Admin login or ?key=DEV_SECRET_KEY)."""
    _verify_dev_key(key, request)
    return FileResponse("app/templates/dev_dashboard.html")


@app.get("/api/dev/analytics", include_in_schema=False)
async def developer_analytics_api(request: Request, key: str = Query(""), limit: int = Query(150, ge=1, le=1000)):
    """Return full developer telemetry JSON (returns 404 Not Found without key or Admin login)."""
    _verify_dev_key(key, request)
    data = await asyncio.to_thread(get_developer_analytics, limit)
    return JSONResponse(content=data)


@app.get("/api/dev/image/{image_id}", include_in_schema=False)
async def developer_view_image(image_id: int, request: Request, key: str = Query("")):
    """Stream a privately stored uploaded image for the developer dashboard (returns 404 without key or Admin login)."""
    _verify_dev_key(key, request)
    record = await asyncio.to_thread(get_image_blob_by_id, image_id)
    if not record:
        raise HTTPException(status_code=404, detail="Image not found")
    img_bytes, content_type, _ = record
    return Response(content=img_bytes, media_type=content_type)


class VerifyImagePayload(BaseModel):
    image_id: int
    verified_label: str
    developer_notes: str = ""


class GeminiKeyPayload(BaseModel):
    api_key: str


@app.get("/api/dev/gemini-keys", include_in_schema=False)
async def developer_list_gemini_keys(request: Request, key: str = Query("")):
    """Return masked Gemini API keys currently active in the rotation pool."""
    _verify_dev_key(key, request)
    keys, model_name = _get_gemini_key_pool_and_model()
    masked = [f"{k[:7]}...{k[-4:]}" if len(k) > 12 else "***" for k in keys]
    return {"status": "ok", "count": len(keys), "masked_keys": masked, "primary_model": model_name}


@app.post("/api/dev/gemini-keys", include_in_schema=False)
async def developer_add_gemini_key(payload: GeminiKeyPayload, request: Request, key: str = Query("")):
    """Add a backup Gemini API key to the runtime rotation pool (data/gemini_keys.json)."""
    _verify_dev_key(key, request)
    new_k = (payload.api_key or "").strip()
    if len(new_k) < 20 or not new_k.startswith("AIza"):
        raise HTTPException(status_code=400, detail="مفتاح Gemini API غير صالح (يجب أن يبدأ بـ AIza).")

    _GEMINI_KEYS_FILE.parent.mkdir(parents=True, exist_ok=True)
    saved_keys: List[str] = []
    if _GEMINI_KEYS_FILE.exists():
        try:
            saved_keys = list(json.loads(_GEMINI_KEYS_FILE.read_text(encoding="utf-8")).get("keys", []))
        except Exception:
            saved_keys = []
    if new_k not in saved_keys:
        saved_keys.append(new_k)
    _GEMINI_KEYS_FILE.write_text(json.dumps({"keys": saved_keys}, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        os.chmod(str(_GEMINI_KEYS_FILE), 0o600)
    except Exception:
        pass

    keys, model_name = _get_gemini_key_pool_and_model()
    masked = [f"{k[:7]}...{k[-4:]}" if len(k) > 12 else "***" for k in keys]
    return {"status": "ok", "count": len(keys), "masked_keys": masked, "primary_model": model_name}


@app.post("/api/dev/verify-image", include_in_schema=False)
async def developer_verify_image(payload: VerifyImagePayload, request: Request, key: str = Query("")):
    """Allow the developer to verify or relabel an uploaded image for Active Learning retraining."""
    _verify_dev_key(key, request)
    ok = await asyncio.to_thread(
        update_image_ground_truth,
        payload.image_id,
        payload.verified_label,
        payload.developer_notes,
    )
    return {"status": "ok" if ok else "not_found", "image_id": payload.image_id}


@app.get("/api/dev/export/{export_type}", include_in_schema=False)
async def developer_export_data(export_type: str, request: Request, key: str = Query("")):
    """Export telemetry tables as JSON, UTF-8-BOM CSV, Retraining Dataset ZIP, or Fine-Tuning JSONL."""
    _verify_dev_key(key, request)

    if export_type == "dataset_zip":
        zip_bytes = await asyncio.to_thread(build_retraining_zip)
        return Response(
            content=zip_bytes,
            media_type="application/zip",
            headers={"Content-Disposition": 'attachment; filename="plant_disease_retraining_dataset.zip"'},
        )

    if export_type == "finetune_jsonl":
        jsonl_bytes = await asyncio.to_thread(build_rag_finetuning_jsonl)
        return Response(
            content=jsonl_bytes,
            media_type="application/jsonl; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="agri_rag_finetuning_dataset.jsonl"'},
        )

    data = await asyncio.to_thread(get_developer_analytics, 1000)

    if export_type == "json":
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        return Response(
            content=body,
            media_type="application/json; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="developer_telemetry.json"'},
        )

    output = io.StringIO()
    output.write("\ufeff")  # UTF-8 BOM for Excel Arabic support
    writer = csv.writer(output)

    if export_type == "chats_csv":
        writer.writerow([
            "ID", "التاريخ", "المستخدم", "حساب المستخدم", "IP", "المدينة/الشبكة", "الجهاز", "المحافظة", "المحصول",
            "تصنيف السؤال", "فجوة معرفية؟", "المحرك", "السؤال", "الإجابة", "الثقة", "الزمن (ms)", "الحالة"
        ])
        for c in data.get("recent_chats", []):
            writer.writerow([
                c.get("id"), c.get("created_at"), c.get("user_name") or "زائر", c.get("user_identifier") or "",
                c.get("client_ip"),
                f"{c.get('geo_city', '')} ({c.get('isp', '')})", c.get("device_type"),
                c.get("location"), c.get("crop"), c.get("topic_category"),
                "نعم" if c.get("is_knowledge_gap") else "لا", c.get("rag_engine"),
                c.get("user_query"), c.get("bot_answer"), c.get("confidence"),
                c.get("latency_ms"), c.get("status"),
            ])
        filename = "chat_logs.csv"
    elif export_type == "images_csv":
        writer.writerow([
            "ID", "التاريخ", "المستخدم", "حساب المستخدم", "اسم الملف", "IP", "المدينة/الشبكة", "الجهاز", "الموديل",
            "المرض المتوقع (عربي)", "المرض المتوقع (EN)", "التصحيح المعتمد (Ground Truth)",
            "الثقة", "هامش الثقة (Margin%)", "يحتاج مراجعة؟", "الأبعاد", "الحجم KB",
            "حدة الصورة (Blur)", "الإضاءة", "نسبة الأوراق الخضراء%", "تقييم الجودة",
            "كاميرا EXIF", "الزمن (ms)", "التوصية"
        ])
        for img in data.get("recent_images", []):
            writer.writerow([
                img.get("id"), img.get("created_at"), img.get("user_name") or "زائر", img.get("user_identifier") or "",
                img.get("filename"), img.get("client_ip"),
                f"{img.get('geo_city', '')} ({img.get('isp', '')})", img.get("device_type"),
                img.get("model_used"), img.get("predicted_class_ar"), img.get("predicted_class"),
                img.get("verified_label"), img.get("confidence"), img.get("margin_score"),
                "نعم" if img.get("is_uncertain") else "لا",
                f"{img.get('width', 0)}x{img.get('height', 0)}", img.get("file_size_kb"),
                img.get("blur_score"), img.get("brightness_score"), img.get("green_ratio"),
                img.get("quality_flag"), img.get("exif_camera"), img.get("latency_ms"),
                img.get("rag_advice"),
            ])
        filename = "uploaded_images_forensics.csv"
    elif export_type == "users_csv":
        writer.writerow([
            "ID", "الاسم", "رقم الموبايل / الإيميل", "الموبايل", "البريد الإلكتروني",
            "المحافظة", "المحصول الأساسي", "الصلاحية", "مرات الدخول",
            "عدد الصور المفحوصة", "عدد استشارات الشات", "تاريخ التسجيل", "آخر دخول", "IP", "الجهاز"
        ])
        for u in data.get("registered_users", []):
            writer.writerow([
                u.get("id"), u.get("full_name"), u.get("identifier"), u.get("phone"), u.get("email"),
                u.get("governorate"), u.get("primary_crop"), u.get("role"), u.get("login_count"),
                u.get("images_count", 0), u.get("chats_count", 0), u.get("created_at"),
                u.get("last_login_at"), u.get("client_ip"), u.get("device_type"),
            ])
        filename = "registered_users.csv"
    else:
        raise HTTPException(status_code=404, detail="Not Found")

    return Response(
        content=output.getvalue().encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

