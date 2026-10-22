"""Speech-to-Text & Text-to-Speech Endpoints (Egyptian Dialect).

Provides:
- POST /api/stt: Spoken Egyptian dialect transcription using Gemini rotation with WebSpeech fallback
- GET /api/tts: Neural Egyptian speech synthesis (MP3/WAV)
- POST /api/tts: Long prescription Egyptian speech synthesis (MP3/WAV)
"""

from __future__ import annotations

import logging
from typing import Dict, Optional

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile

from app.core.rate_limiter import ai_audio_limiter
from app.schemas.chat import TTSPayload
from app.services.audio_service import synthesize_speech, transcribe_speech

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/api/stt", tags=["Speech (Egyptian Dialect)"])
async def egyptian_stt_endpoint(
    audio: Optional[UploadFile] = File(None),
    fallback_text: str = Form(""),
    _rate_limit: bool = Depends(ai_audio_limiter),
) -> Dict[str, str]:
    """Transcribe spoken Egyptian Arabic audio into Egyptian agricultural dialect text with multi-key rotation."""
    audio_bytes = None
    content_type = "audio/webm"
    if audio is not None:
        audio_bytes = await audio.read()
        content_type = audio.content_type or "audio/webm"

    return await transcribe_speech(
        audio_bytes, content_type=content_type, fallback_text=fallback_text
    )


@router.get("/api/tts", tags=["Speech (Egyptian Dialect)"])
async def egyptian_tts_get_endpoint(
    text: str = Query(..., description="النص المراد نطقه باللهجة المصرية"),
    voice: str = Query(
        "ar-EG-ShakirNeural",
        description="ar-EG-ShakirNeural (رجالي مصري) أو ar-EG-SalmaNeural (نسائي مصري)",
    ),
) -> Response:
    """Synthesize natural Egyptian Arabic speech (MP3/WAV) via GET."""
    audio_bytes, media_type = await synthesize_speech(text, voice)
    return Response(
        content=audio_bytes,
        media_type=media_type,
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.post("/api/tts", tags=["Speech (Egyptian Dialect)"])
async def egyptian_tts_post_endpoint(
    payload: TTSPayload,
    _rate_limit: bool = Depends(ai_audio_limiter),
) -> Response:
    """Synthesize natural Egyptian Arabic speech (MP3/WAV) via POST (supports long agricultural prescriptions)."""
    audio_bytes, media_type = await synthesize_speech(payload.text, payload.voice)
    return Response(content=audio_bytes, media_type=media_type)
