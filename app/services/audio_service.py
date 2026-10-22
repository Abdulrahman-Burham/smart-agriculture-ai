"""Audio Service: Egyptian Dialect Speech-to-Text & Neural Text-to-Speech.

Provides:
- Spoken Egyptian Arabic dialect normalization and phonetic transformations
- Multi-key Gemini Audio STT with browser WebSpeech normalization fallback
- Gemini 3.8 Neural Egyptian TTS with Microsoft Edge Neural TTS retry fallback
- Audio format converters (PCM / WAV to MP3) and in-memory response caching
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import io
import logging
import re
import time
import wave
from typing import Dict, List, Optional, Tuple

import requests as ext_requests
from fastapi import HTTPException

from app.services.llm_service import get_gemini_key_pool_and_model
from computer_vision.storage.telemetry_repository import save_token_usage_log
from computer_vision.storage.utils import estimate_tokens, mask_api_key

logger = logging.getLogger(__name__)

_STT_KEY_RR_IDX: int = 0
_TTS_KEY_RR_IDX: int = 0
_TTS_AUDIO_CACHE: Dict[Tuple[str, str], bytes] = {}

EGYPTIAN_STT_PROMPT = """أنت نموذج متخصص في تحويل الكلام العربي المنطوق باللهجة المصرية الزراعية إلى نص مكتوب.
استمع للملف الصوتي بدقة، واكتب ما قاله المزارع بالعامية المصرية الدقيقة دون تحريف أو تصحيح للفصحى.
إذا ذكر أسماء محاصيل، أمراض زراعية (مثل الندوة، البياض، سوسة النخيل)، أو مبيدات (مثل كبريت، نحاس، ريدوميل)، اكتبها كما تُنطق في الحقل المصري.
اكتب النص المنطوق فقط بدون أي مقدمات أو شروحات إضافية."""

_SPOKEN_EGYPTIAN_PHRASE_MAP: List[Tuple[str, str]] = [
    ("تم تشخيص:", "بص يا باشمهندس، نتيجة الفحص هي:"),
    ("نتيجة التشخيص:", "بص يا ريس، نتيجة الفحص هي:"),
    ("بناءً على التشخيص", "على حسب الفحص"),
    ("بناءً على ", "على حسب "),
    ("وفقاً لـ", "على حسب "),
    ("بثقة ", "بنسبة تأكيد "),
    ("خطة العلاج والجرعات الموصى بها:", "ودلوقتي دي خطة العلاج والجرعات المظبوطة،"),
    ("خطوات العلاج والمكافحة:", "خطوات العلاج اللي هتعملها في الأرض،"),
    ("المكافحة الكيميائية:", "بالنسبة للرش والمبيدات،"),
    ("المكافحة الزراعية:", "وبالنسبة للمعاملات في الأرض،"),
    ("الوقاية والاحتياطات:", "وعلشان تحمي زرعك،"),
    ("بشمهندس", "باشمهندس"),
    ("يجب عليك ", "لازم "),
    ("يجب أن ", "لازم "),
    ("يجب ", "لازم "),
    ("ينبغي عليك ", "لازم "),
    ("ينبغي ", "لازم "),
    ("يتوجب عليك ", "لازم "),
    ("لا بد من ", "لازم "),
    ("لابد من ", "لازم "),
    ("يلزم ", "لازم "),
    ("يُنصح بـ", "بننصحك بـ"),
    ("ينصح بـ", "بننصحك بـ"),
    ("يُنصح ", "بننصحك "),
    ("ينصح ", "بننصحك "),
    ("يوصى بـ", "الأحسن "),
    ("يُوصى بـ", "الأحسن "),
    ("نوصي بـ", "بننصحك بـ"),
    ("الموصى بها", "اللي بننصح بيها"),
    ("الموصى به", "اللي بننصح بيه"),
    ("يفضل ", "الأحسن "),
    ("يُفضل ", "الأحسن "),
    ("من الأفضل ", "الأحسن "),
    ("قم برش ", "رش "),
    ("قم بإزالة ", "شيل "),
    ("قم بري ", "اروي "),
    ("قم بتقليل ", "قلل "),
    ("قم بـ", "اعمل "),
    ("يتم رش ", "هترش "),
    ("يتم ري ", "تروي "),
    ("يتم استخدام ", "تستخدم "),
    ("يمكنك استخدام ", "تقدر تستخدم "),
    ("يمكنك ", "تقدر "),
    ("في الصباح الباكر", "الصبح بدري قبل الشمس"),
    ("عند الغروب", "وقت العصرية أو قبل الغروب"),
    ("خلال ", "خلال "),
    ("لتجنب ", "علشان تتجنب "),
    ("لكي ", "علشان "),
    ("حتى لا ", "علشان ما "),
    ("سوف ", "هـ"),
    ("ستؤدي ", "هتسبب "),
    ("سوف يؤدي ", "هيسبب "),
    ("أيضاً", "كمان"),
    ("ايضا", "كمان"),
    ("جداً", "قوي"),
    ("جدًا", "قوي"),
    ("فقط", "بس"),
    ("لكن", "بس"),
    ("ولكن", "بس"),
    ("الآن", "دلوقتي"),
    ("سريعاً", "بسرعة"),
    ("سريعا", "بسرعة"),
    ("فوراً", "على طول"),
    ("فورا", "على طول"),
]


def normalize_to_egyptian_dialect(text: str) -> str:
    """Normalize input text to Egyptian agricultural dialect."""
    t = text or ""
    t = re.sub(r"[\*#_`~>\[\]]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def to_spoken_egyptian_arabic(text: str) -> str:
    """Translate formal Arabic text into authentic Egyptian agricultural dialect."""
    t = normalize_to_egyptian_dialect(text)
    for f, r in _SPOKEN_EGYPTIAN_PHRASE_MAP:
        t = t.replace(f, r)
    return t


def wav_or_pcm_to_mp3(
    audio_bytes: bytes, sample_rate: int = 24000, channels: int = 1
) -> Tuple[bytes, str]:
    """Convert raw PCM or WAV audio bytes to MP3 or return standard WAV."""
    if audio_bytes[:4] == b"RIFF":
        try:
            with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
                sample_rate = wf.getframerate()
                channels = wf.getnchannels()
                pcm_data = wf.readframes(wf.getnframes())
        except Exception:
            pcm_data = audio_bytes[44:]
    else:
        pcm_data = audio_bytes

    try:
        import lameenc

        encoder = lameenc.Encoder()
        encoder.set_bit_rate(64)
        encoder.set_in_sample_rate(sample_rate)
        encoder.set_channels(channels)
        encoder.set_quality(2)
        mp3_bytes = bytes(encoder.encode(pcm_data) + encoder.flush())
        if mp3_bytes:
            return mp3_bytes, "audio/mpeg"
    except Exception:
        pass

    if audio_bytes[:4] == b"RIFF":
        return audio_bytes, "audio/wav"

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)
    return buf.getvalue(), "audio/wav"


async def transcribe_speech(
    audio_bytes: Optional[bytes],
    content_type: str = "audio/webm",
    fallback_text: str = "",
) -> Dict[str, str]:
    """Transcribe spoken Egyptian Arabic audio using Gemini rotation pool with WebSpeech fallback."""
    global _STT_KEY_RR_IDX

    if audio_bytes and len(audio_bytes) > 200:
        keys, cfg_model = get_gemini_key_pool_and_model()
        if keys:
            n_keys = len(keys)
            start_idx = _STT_KEY_RR_IDX % n_keys
            _STT_KEY_RR_IDX += 1
            ordered_pairs = [
                ((start_idx + i) % n_keys + 1, keys[(start_idx + i) % n_keys])
                for i in range(n_keys)
            ]

            mime_type = (content_type or "audio/webm").split(";")[0].strip().lower()
            if mime_type in ("audio/x-m4a", "audio/m4a", "audio/aac"):
                mime_type = "audio/mp4"
            elif mime_type not in (
                "audio/webm",
                "audio/mp4",
                "audio/ogg",
                "audio/wav",
                "audio/mpeg",
                "audio/mp3",
            ):
                mime_type = "audio/webm"
            b64_audio = base64.b64encode(audio_bytes).decode("ascii")

            def _call_gemini_stt() -> str:
                models = [
                    cfg_model,
                    "gemini-3.8-flash",
                    "gemini-3.5-flash-lite",
                    "gemini-2.5-flash",
                ]
                for k_idx, api_key in ordered_pairs:
                    key_mask = mask_api_key(api_key, k_idx)
                    for m in models:
                        t0 = time.time()
                        try:
                            url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={api_key}"
                            payload = {
                                "contents": [
                                    {
                                        "parts": [
                                            {"text": EGYPTIAN_STT_PROMPT},
                                            {
                                                "inlineData": {
                                                    "mimeType": mime_type,
                                                    "data": b64_audio,
                                                }
                                            },
                                        ]
                                    }
                                ],
                                "generationConfig": {
                                    "temperature": 0.1,
                                    "maxOutputTokens": 250,
                                },
                            }
                            r = ext_requests.post(url, json=payload, timeout=15)
                            call_ms = round((time.time() - t0) * 1000, 1)
                            if r.status_code == 200:
                                resp_json = r.json()
                                usage = resp_json.get("usageMetadata") or {}
                                candidates = resp_json.get("candidates", [])
                                if candidates:
                                    parts = (
                                        candidates[0]
                                        .get("content", {})
                                        .get("parts", [])
                                    )
                                    if parts and parts[0].get("text"):
                                        out_txt = parts[0]["text"].strip()
                                        p_tok = int(
                                            usage.get("promptTokenCount") or 220
                                        )
                                        c_tok = int(
                                            usage.get("candidatesTokenCount")
                                            or estimate_tokens(out_txt)
                                        )
                                        t_tok = int(
                                            usage.get("totalTokenCount")
                                            or (p_tok + c_tok)
                                        )
                                        save_token_usage_log(
                                            endpoint="/api/stt",
                                            service_type="stt_audio",
                                            model_name=m,
                                            api_key_masked=key_mask,
                                            prompt_tokens=p_tok,
                                            completion_tokens=c_tok,
                                            total_tokens=t_tok,
                                            latency_ms=call_ms,
                                            status="success",
                                            query_preview=out_txt[:140],
                                        )
                                        return out_txt
                            elif r.status_code == 429:
                                save_token_usage_log(
                                    endpoint="/api/stt",
                                    service_type="stt_audio",
                                    model_name=m,
                                    api_key_masked=key_mask,
                                    prompt_tokens=0,
                                    completion_tokens=0,
                                    total_tokens=0,
                                    latency_ms=call_ms,
                                    status="rate_limited_429",
                                    query_preview="HTTP 429 Rate Limit on STT",
                                )
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

    cleaned = normalize_to_egyptian_dialect(fallback_text)
    return {
        "text": cleaned,
        "dialect": "ar-EG",
        "engine": "WebSpeech ar-EG + Egyptian Dialect Normalizer",
    }


async def synthesize_speech(
    raw_text: str, voice: str = "ar-EG-ShakirNeural"
) -> Tuple[bytes, str]:
    """Synthesize authentic Egyptian speech using Gemini Neural TTS with Microsoft Edge fallback."""
    global _TTS_KEY_RR_IDX

    base_spoken = to_spoken_egyptian_arabic(raw_text)
    if not base_spoken:
        raise HTTPException(status_code=400, detail="Empty text")

    is_female = voice in ("ar-EG-SalmaNeural", "female", "Aoede", "Kore")
    selected_edge_voice = "ar-EG-SalmaNeural" if is_female else "ar-EG-ShakirNeural"
    gemini_voice = "Aoede" if is_female else "Orus"

    clipped_text = base_spoken[:900]
    raw_hash = hashlib.md5(clipped_text.encode("utf-8")).hexdigest()
    cache_key = (raw_hash, selected_edge_voice)
    if cache_key in _TTS_AUDIO_CACHE:
        cached_bytes = _TTS_AUDIO_CACHE[cache_key]
        mime = "audio/wav" if cached_bytes[:4] == b"RIFF" else "audio/mpeg"
        return cached_bytes, mime

    # 1. Primary Engine: Gemini Neural TTS
    keys, _ = get_gemini_key_pool_and_model()
    if keys:
        n_keys = len(keys)
        start_idx = _TTS_KEY_RR_IDX % n_keys
        _TTS_KEY_RR_IDX += 1
        ordered_pairs = [
            ((start_idx + i) % n_keys + 1, keys[(start_idx + i) % n_keys])
            for i in range(n_keys)
        ]

        def _call_gemini_tts() -> Optional[Tuple[bytes, str]]:
            for k_idx, api_key in ordered_pairs:
                key_mask = mask_api_key(api_key, k_idx)
                for tts_model in (
                    "gemini-3.8-flash-lite-tts",
                    "gemini-3.8-flash-tts",
                    "gemini-2.5-flash-preview-tts",
                ):
                    t0 = time.time()
                    try:
                        url = f"https://generativelanguage.googleapis.com/v1beta/models/{tts_model}:generateContent?key={api_key}"
                        payload = {
                            "contents": [{"parts": [{"text": clipped_text}]}],
                            "generationConfig": {
                                "responseModalities": ["AUDIO"],
                                "speechConfig": {
                                    "voiceConfig": {
                                        "prebuiltVoiceConfig": {
                                            "voiceName": gemini_voice
                                        }
                                    }
                                },
                            },
                        }
                        r = ext_requests.post(url, json=payload, timeout=16)
                        call_ms = round((time.time() - t0) * 1000, 1)
                        if r.status_code == 200:
                            resp_json = r.json()
                            usage = resp_json.get("usageMetadata") or {}
                            cands = resp_json.get("candidates", [])
                            if cands and "content" in cands[0]:
                                parts = cands[0]["content"].get("parts", [])
                                if parts and parts[0].get("inlineData", {}).get("data"):
                                    raw_audio = base64.b64decode(
                                        parts[0]["inlineData"]["data"]
                                    )
                                    if raw_audio and len(raw_audio) > 400:
                                        p_tok = int(
                                            usage.get("promptTokenCount")
                                            or estimate_tokens(clipped_text)
                                        )
                                        c_tok = int(
                                            usage.get("candidatesTokenCount") or 220
                                        )
                                        t_tok = int(
                                            usage.get("totalTokenCount")
                                            or (p_tok + c_tok)
                                        )
                                        save_token_usage_log(
                                            endpoint="/api/tts",
                                            service_type="tts_audio",
                                            model_name=tts_model,
                                            api_key_masked=key_mask,
                                            prompt_tokens=p_tok,
                                            completion_tokens=c_tok,
                                            total_tokens=t_tok,
                                            latency_ms=call_ms,
                                            status="success",
                                            query_preview=clipped_text[:140],
                                        )
                                        return wav_or_pcm_to_mp3(raw_audio)
                        elif r.status_code == 429:
                            save_token_usage_log(
                                endpoint="/api/tts",
                                service_type="tts_audio",
                                model_name=tts_model,
                                api_key_masked=key_mask,
                                prompt_tokens=0,
                                completion_tokens=0,
                                total_tokens=0,
                                latency_ms=call_ms,
                                status="rate_limited_429",
                                query_preview="HTTP 429 Rate Limit on Gemini TTS",
                            )
                    except Exception as e:
                        logger.warning(f"Gemini TTS ({tts_model}) notice: {e}")
            return None

        gemini_res = await asyncio.to_thread(_call_gemini_tts)
        if gemini_res:
            audio_bytes, media_type = gemini_res
            if len(_TTS_AUDIO_CACHE) > 160:
                _TTS_AUDIO_CACHE.clear()
            _TTS_AUDIO_CACHE[cache_key] = audio_bytes
            return audio_bytes, media_type

    # 2. Secondary Engine: Microsoft Edge Neural TTS with 3x Retry
    edge_text = (
        clipped_text.replace("عشان", "علشان")
        .replace("يا حاج", "يا حَاجّ")
        .replace("خلي بالك", "خَلِّي بَالَك")
        .replace("بتاعتك", "بِتَاعْتَك")
    )
    try:
        import edge_tts
        from edge_tts.drm import DRM

        for attempt in range(3):
            t0_edge = time.time()
            try:
                if attempt > 0:
                    DRM.clock_skew_seconds = 0.0
                communicate = edge_tts.Communicate(
                    edge_text, selected_edge_voice, rate="+0%", pitch="-2Hz"
                )
                audio_chunks = bytearray()
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        audio_chunks.extend(chunk["data"])
                if audio_chunks:
                    mp3_bytes = bytes(audio_chunks)
                    if len(_TTS_AUDIO_CACHE) > 160:
                        _TTS_AUDIO_CACHE.clear()
                    _TTS_AUDIO_CACHE[cache_key] = mp3_bytes
                    asyncio.create_task(
                        asyncio.to_thread(
                            save_token_usage_log,
                            endpoint="/api/tts",
                            service_type="tts_audio",
                            model_name=f"Edge-TTS ({selected_edge_voice})",
                            api_key_masked="Edge Neural (Free Fallback)",
                            prompt_tokens=estimate_tokens(clipped_text),
                            completion_tokens=0,
                            latency_ms=round((time.time() - t0_edge) * 1000, 1),
                            status="success",
                            query_preview=clipped_text[:140],
                        )
                    )
                    return mp3_bytes, "audio/mpeg"
            except Exception as inner_e:
                logger.warning(f"Edge TTS attempt {attempt + 1} notice: {inner_e}")
                await asyncio.sleep(0.15)
    except Exception as e:
        logger.warning(f"Edge TTS notice: {e}")

    raise HTTPException(status_code=503, detail="TTS service unavailable")
