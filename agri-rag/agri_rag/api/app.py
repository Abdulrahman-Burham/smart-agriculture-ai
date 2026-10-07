"""FastAPI application: chat (JSON + SSE streaming), alerts, admin reindex, health."""
from __future__ import annotations

import asyncio
import json
import secrets
from collections.abc import AsyncIterator

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import StreamingResponse

from ..container import Container, build_container
from ..ingestion.indexer import index_directory
from .schemas import (AlertsRequest, AlertsResponse, ChatRequest, ChatResponse,
                      ReindexRequest, ReindexResponse)


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def create_app(container: Container | None = None) -> FastAPI:
    app = FastAPI(title="AgriTech RAG Assistant", version="1.0.0",
                  description="مساعد زراعي خبير (RAG + LLM) يدعم اللهجة المصرية")
    c = container or build_container()
    app.state.container = c

    def auth(x_api_key: str | None = Header(None)) -> None:
        expected = c.settings.api_key
        if expected and not (x_api_key and secrets.compare_digest(x_api_key, expected)):
            raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key")

    @app.get("/healthz")
    async def healthz() -> dict:
        return {"status": "ok", "chunks": c.store.count(), "llm": c.settings.llm_provider,
                "model": c.settings.llm_model}

    @app.post("/v1/chat", response_model=ChatResponse, dependencies=[Depends(auth)])
    async def chat(req: ChatRequest) -> ChatResponse:
        res = await c.pipeline.ask(req.question, req.session_id, req.farm, req.crop)
        return ChatResponse(answer=res.answer, grounded=res.grounded, session_id=res.session_id,
                            sources=res.sources, cited_ids=res.cited_ids, timings=res.timings)

    @app.post("/v1/chat/stream", dependencies=[Depends(auth)])
    async def chat_stream(req: ChatRequest, request: Request) -> StreamingResponse:
        async def events() -> AsyncIterator[str]:
            try:
                async for ev in c.pipeline.stream(req.question, req.session_id, req.farm, req.crop):
                    if await request.is_disconnected():
                        return
                    kind = ev.pop("type")
                    yield _sse(kind, ev)
            except Exception as exc:  # surface a clean error event instead of a dropped socket
                yield _sse("error", {"message": "تعذر إكمال الإجابة حاليًا، حاول مرة أخرى.", "detail": type(exc).__name__})

        return StreamingResponse(events(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.post("/v1/alerts/evaluate", response_model=AlertsResponse, dependencies=[Depends(auth)])
    async def alerts(req: AlertsRequest) -> AlertsResponse:
        found = await c.alert_agent.run(req.farm, enrich=req.enrich)
        return AlertsResponse(farm_id=req.farm.farm_id, alerts=found)

    @app.post("/v1/admin/reindex", response_model=ReindexResponse, dependencies=[Depends(auth)])
    async def reindex(req: ReindexRequest) -> ReindexResponse:
        report = await asyncio.to_thread(index_directory, c.settings.knowledge_dir, c.store, c.settings, req.reset)
        await asyncio.to_thread(c.retriever.refresh)
        return ReindexResponse(**report.__dict__)

    return app


def app_factory() -> FastAPI:  # uvicorn --factory agri_rag.api.app:app_factory
    return create_app()
