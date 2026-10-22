"""Agricultural Q&A Chat & Memory Endpoints.

Provides:
- GET /api/chat/memory: Load multi-turn persistent conversation memory and recent diagnoses
- POST /api/chat: Agri-RAG powered agricultural assistant with persistent memory, telemetry, and guest gating
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.core.guest_policy import enforce_guest_gate_or_401
from app.core.rate_limiter import ai_chat_limiter
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.llm_service import (
    IRRIG_TO_ENUM,
    KNOWN_AGRI_RAG_CROPS,
    format_agri_rag_sources,
    get_rag_pipeline,
    query_agri_rag,
)
from computer_vision.storage.chat_repository import get_agent_memory_context, save_chat_log
from computer_vision.storage.telemetry_repository import save_error_log
from computer_vision.storage.utils import extract_client_info, extract_user_from_request

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/chat/memory", tags=["RAG"])
async def get_chat_memory_endpoint(
    http_request: Request,
    session_id: str = Query(""),
    limit: int = Query(15, ge=1, le=50),
) -> Dict[str, Any]:
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


@router.post("/api/chat", response_model=ChatResponse, tags=["RAG"])
async def chat_endpoint(
    request: ChatRequest,
    http_request: Request,
    _rate_limit: bool = Depends(ai_chat_limiter),
) -> ChatResponse:
    """Agri-RAG powered agricultural Q&A chat endpoint with persistent multi-turn memory and silent telemetry."""
    start_time = time.time()
    client_info = extract_client_info(http_request)
    auth_user = extract_user_from_request(http_request)
    u_id = int(auth_user["uid"]) if auth_user and auth_user.get("uid") else None
    u_name = auth_user.get("name", "") if auth_user else ""
    u_ident = auth_user.get("identifier", "") if auth_user else ""

    await enforce_guest_gate_or_401(client_info, u_id, "/api/chat")

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
            from rag.tools import get_current_date_context, get_weather
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
        irrig_enum = IRRIG_TO_ENUM.get(raw_irrig.strip())

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
        llm_tel = agri_data.get("_llm_telemetry") or {}

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
                prompt_tokens=int(llm_tel.get("prompt_tokens") or 0),
                completion_tokens=int(llm_tel.get("completion_tokens") or 0),
                total_tokens=int(llm_tel.get("total_tokens") or 0),
                api_key_masked=str(llm_tel.get("api_key_masked") or ""),
                llm_model=str(llm_tel.get("model_name") or "gemini-2.5-flash"),
            )
        )

        return ChatResponse(
            answer=answer_text,
            weather="",
            sources=sources,
            confidence=top_conf,
            latency=latency,
            intent=agri_data.get("intent") or "agri_rag",
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
