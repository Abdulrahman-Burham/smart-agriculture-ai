"""Unified FastAPI Gateway: RAG + Computer Vision + Dashboard for Smart Agriculture AI MVP."""

from __future__ import annotations

import io
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.responses import FileResponse

load_dotenv()

logger = logging.getLogger(__name__)

# ─── Pydantic Schemas ───────────────────────────────────────────────

class ChatRequest(BaseModel):
    query: str
    location: str = "Cairo"

class ChatResponse(BaseModel):
    answer: str
    weather: str = ""
    sources: List[str] = []
    confidence: float = 0.0
    latency: float = 0.0
    intent: str = ""

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

class WeatherResponse(BaseModel):
    temperature: Optional[float] = None
    wind_speed: Optional[float] = None
    season: str = ""
    date: str = ""

class HealthResponse(BaseModel):
    status: str = "healthy"
    services: Dict[str, str] = {}
    version: str = "2.0.0-mvp"


# ─── Initialize FastAPI ─────────────────────────────────────────────

app = FastAPI(
    title="الخبير الزراعي — Smart Agriculture AI",
    description="Unified MVP: RAG + Computer Vision + Dashboard",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for dashboard
app.mount("/static", StaticFiles(directory="app/static"), name="static")


# ─── Lazy Globals (initialized on first request) ────────────────────

_rag_pipeline = None
_cv_classifier = None


def get_rag_pipeline():
    """Lazily initialize and return the RAG pipeline with auto-wired LLM."""
    global _rag_pipeline
    if _rag_pipeline is None:
        from rag.respond import RAGPipeline
        _rag_pipeline = RAGPipeline(config_path="rag/config.yaml", lexicon_path="rag/lexicon.json")

        # Auto-wire Groq LLM if API key exists
        groq_key = os.environ.get("GROQ_API_KEY")
        if groq_key:
            from rag.generate import GroqLLMProvider
            _rag_pipeline.llm_provider = GroqLLMProvider(api_key=groq_key)
            logger.info("✅ Groq LLM auto-wired successfully.")
        else:
            logger.warning("⚠️ GROQ_API_KEY not found. Using MockLLMProvider.")

        # Auto-ingest PDF knowledge base
        pdf_path = Path("التوصيات_المعتمدة_لمكافحة_الآفات_الزراعية.pdf")
        if pdf_path.exists():
            logger.info("📚 Ingesting PDF knowledge base...")
            _rag_pipeline.ingest_pdfs([str(pdf_path)])
            logger.info("✅ PDF ingestion complete.")

        # Also ingest sample text docs
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
                logger.info(f"📚 Ingested {len(docs)} text documents.")

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


import asyncio

# ─── Routes ──────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
@app.head("/", include_in_schema=False)
@app.get("/dashboard", include_in_schema=False)
@app.head("/dashboard", include_in_schema=False)
async def serve_dashboard():
    """Serve the unified MVP dashboard."""
    return FileResponse("app/static/index.html")


@app.get("/simple", include_in_schema=False)
@app.head("/simple", include_in_schema=False)
async def serve_simple_ui():
    """Serve isolated simple 2-button image diagnosis interface."""
    return FileResponse("app/static/simple.html")


@app.get("/health", response_model=HealthResponse, tags=["System"])
@app.head("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """System health and readiness probe."""
    cv = get_cv_classifier()
    return HealthResponse(
        status="healthy",
        services={
            "api_gateway": "online",
            "rag_pipeline": "online",
            "cv_model": "online" if cv else "offline",
            "vector_store": "online" if os.environ.get("QDRANT_URL") else "local",
        },
    )


@app.get("/api/weather", response_model=WeatherResponse, tags=["Tools"])
async def get_weather_endpoint():
    """Get current weather and agricultural season."""
    from rag.tools import get_weather, get_current_date_context
    import datetime

    weather = await asyncio.to_thread(get_weather)
    date_ctx = await asyncio.to_thread(get_current_date_context)

    return WeatherResponse(
        temperature=weather.get("temperature"),
        wind_speed=weather.get("wind_speed"),
        season=date_ctx.split("فصل ")[-1].rstrip(".") if "فصل" in date_ctx else "",
        date=datetime.datetime.now().strftime("%Y-%m-%d"),
    )


@app.post("/api/chat", response_model=ChatResponse, tags=["RAG"])
async def chat_endpoint(request: ChatRequest):
    """RAG-powered agricultural Q&A chat endpoint with non-blocking thread execution."""
    start_time = time.time()

    try:
        pipeline = get_rag_pipeline()

        # Enrich query with weather context
        from rag.tools import get_weather, get_current_date_context
        date_context = await asyncio.to_thread(get_current_date_context)
        weather_data = await asyncio.to_thread(get_weather)

        weather_str = ""
        if weather_data.get("status") == "success":
            weather_str = f"درجة الحرارة: {weather_data.get('temperature')}°C، سرعة الرياح: {weather_data.get('wind_speed')} كم/س."

        enriched_query = f"{request.query}\n(معلومة للمساعد: {date_context} {weather_str})"

        result = await asyncio.to_thread(pipeline.run, enriched_query)

        sources = list(set(
            f"صفحة {c.get('metadata', {}).get('page_start', '?')}"
            for c in result.get("sources", [])
        ))

        latency = round(time.time() - start_time, 3)

        return ChatResponse(
            answer=result["answer"],
            weather=weather_str,
            sources=sources,
            confidence=round(result.get("retrieval_confidence", 0), 4),
            latency=latency,
            intent=result.get("intent", ""),
        )
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/diagnose", response_model=DiagnoseResponse, tags=["Vision + RAG"])
async def diagnose_endpoint(
    image: UploadFile = File(...),
    query: str = Form("ما هو المرض وما هو العلاج؟"),
):
    """Upload a leaf image → CV diagnosis + RAG treatment advice with non-blocking execution."""
    start_time = time.time()

    try:
        # Step 1: Read image bytes
        image_bytes = await image.read()
        if not image_bytes:
            raise HTTPException(status_code=400, detail="Empty image file.")

        # Step 2: Run Computer Vision prediction in thread pool
        cv = get_cv_classifier()
        cv_result = {}
        vision_context = None

        if cv:
            image_stream = io.BytesIO(image_bytes)
            prediction = await asyncio.to_thread(cv.predict, image_stream)
            cv_result = prediction

            vision_context = {
                "crop_type": prediction.get("crop_type", ""),
                "disease_label": prediction.get("disease_name", ""),
                "confidence_score": prediction.get("top_confidence", 0),
            }

        # Step 3: Enrich query with CV results and run RAG in thread pool
        pipeline = get_rag_pipeline()

        enriched_query = query
        if vision_context and vision_context.get("crop_type") != "unknown":
            crop_ar = cv_result.get("predictions", [{}])[0].get("label_ar", "")
            enriched_query = f"{query}\n(نتيجة تحليل الصورة: المحصول: {vision_context['crop_type']}، المرض المكتشف: {crop_ar}، الثقة: {vision_context['confidence_score']:.0%})"

        rag_result = await asyncio.to_thread(
            pipeline.run,
            user_query=enriched_query,
            vision_context=vision_context,
        )

        sources = list(set(
            f"صفحة {c.get('metadata', {}).get('page_start', '?')}"
            for c in rag_result.get("sources", [])
        ))

        latency = round(time.time() - start_time, 3)

        return DiagnoseResponse(
            cv_result=cv_result,
            advice=rag_result["answer"],
            sources=sources,
            confidence=round(rag_result.get("retrieval_confidence", 0), 4),
            latency=latency,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Diagnose error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

