"""LLM Service: Gemini API Key Rotation, Agri-RAG Orchestration, and Telemetry.

Manages:
- Multi-key Gemini API rotation pool (`data/gemini_keys.json`) with round-robin dispatch
- OAuth Client ID persistence (`data/oauth_config.json`)
- Multi-tier Agri-RAG integration (HTTP daemon on port 8070 -> in-process container -> local RAG pipeline)
- Live key ping health & quota checks
- Token usage & cost attribution
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests as ext_requests

from app.core.config import AGRI_RAG_URL, DATA_DIR
from computer_vision.storage.telemetry_repository import save_token_usage_log
from computer_vision.storage.utils import estimate_tokens, mask_api_key

logger = logging.getLogger(__name__)

_GEMINI_KEYS_FILE: Path = DATA_DIR / "gemini_keys.json"
_OAUTH_CONFIG_FILE: Path = DATA_DIR / "oauth_config.json"

_RAG_KEY_RR_IDX: int = 0
_local_agri_rag_container: Optional[Any] = None
_rag_pipeline: Optional[Any] = None


def load_oauth_config() -> Dict[str, str]:
    """Load persistent OAuth configuration from data/oauth_config.json or environment fallback."""
    cfg = {
        "google_client_id": os.environ.get("GOOGLE_CLIENT_ID", "").strip(),
        "google_client_secret": os.environ.get("GOOGLE_CLIENT_SECRET", "").strip(),
        "microsoft_client_id": os.environ.get("MICROSOFT_CLIENT_ID", "").strip(),
    }
    if _OAUTH_CONFIG_FILE.exists():
        try:
            saved = json.loads(_OAUTH_CONFIG_FILE.read_text(encoding="utf-8"))
            if saved.get("google_client_id"):
                cfg["google_client_id"] = str(saved["google_client_id"]).strip()
            if saved.get("google_client_secret"):
                cfg["google_client_secret"] = str(saved["google_client_secret"]).strip()
            if saved.get("microsoft_client_id"):
                cfg["microsoft_client_id"] = str(saved["microsoft_client_id"]).strip()
        except Exception:
            pass
    return cfg


def save_oauth_config(google_client_id: Optional[str] = None, microsoft_client_id: Optional[str] = None) -> Dict[str, Any]:
    """Persist OAuth client IDs to data/oauth_config.json."""
    current = load_oauth_config()
    new_cfg = {
        "google_client_id": (google_client_id.strip() if google_client_id is not None else current.get("google_client_id", "")),
        "microsoft_client_id": (microsoft_client_id.strip() if microsoft_client_id is not None else current.get("microsoft_client_id", "")),
        "google_client_secret": current.get("google_client_secret", ""),
    }
    _OAUTH_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    _OAUTH_CONFIG_FILE.write_text(json.dumps(new_cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        os.chmod(str(_OAUTH_CONFIG_FILE), 0o600)
    except Exception:
        pass
    return new_cfg


def get_gemini_key_pool_and_model() -> Tuple[List[str], str]:
    """Collect all configured Gemini API keys from environment and data/gemini_keys.json."""
    keys: List[str] = []
    primary_model = os.environ.get("AGRI_LLM_MODEL", "gemini-2.5-flash")

    for env_var in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "AGRI_GEMINI_KEY"):
        val = os.environ.get(env_var, "").strip()
        if val and val not in keys and val not in ("not-needed", "local"):
            keys.append(val)

    if _GEMINI_KEYS_FILE.exists():
        try:
            cfg = json.loads(_GEMINI_KEYS_FILE.read_text(encoding="utf-8"))
            saved_keys = cfg.get("keys", [])
            for k in saved_keys:
                k_clean = str(k).strip()
                if k_clean and k_clean not in keys:
                    keys.append(k_clean)
            if cfg.get("primary_model"):
                primary_model = str(cfg["primary_model"]).strip()
        except Exception:
            pass

    return keys, primary_model


def get_local_agri_rag() -> Any:
    """Fallback in-process Agri-RAG container if port 8070 service is not running locally."""
    global _local_agri_rag_container
    if _local_agri_rag_container is None:
        agri_rag_dir = Path(__file__).resolve().parent.parent.parent / "agri-rag"
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


def get_rag_pipeline() -> Any:
    """Lazily initialize and return the legacy RAG pipeline."""
    global _rag_pipeline
    if _rag_pipeline is None:
        from rag.respond import RAGPipeline

        logger.info("Initializing Agricultural RAG Pipeline...")
        _rag_pipeline = RAGPipeline()

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


def format_rag_sources(
    raw_sources: List[Dict[str, Any]],
    data: Dict[str, Any],
) -> Tuple[List[str], float]:
    """Format and de-duplicate citations returned by Agri-RAG with top similarity score."""
    selected = raw_sources[:4] if raw_sources else []
    cited_ids = set(data.get("cited_ids") or [])
    if cited_ids and raw_sources:
        cited_sources = [s for s in raw_sources if s.get("id") in cited_ids]
        if cited_sources:
            selected = cited_sources

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


def build_rag_llm_telemetry(question: str, out_data: Dict[str, Any]) -> Dict[str, Any]:
    """Compute token usage, model name, and round-robin API key mask for an Agri-RAG call."""
    global _RAG_KEY_RR_IDX
    keys, model_name = get_gemini_key_pool_and_model()
    if keys:
        idx = _RAG_KEY_RR_IDX % len(keys)
        _RAG_KEY_RR_IDX += 1
        key_mask = mask_api_key(keys[idx], idx + 1)
    else:
        key_mask = "Local / Fallback (No Key)"

    answer = str(out_data.get("answer") or "")
    sources = out_data.get("sources") or []
    sources_text = " ".join(
        f"{s.get('title', '')} {s.get('section', '')} {s.get('snippet', '')}" for s in sources if isinstance(s, dict)
    )
    p_tok = int(out_data.get("prompt_tokens") or (estimate_tokens(question) + estimate_tokens(sources_text) + 640))
    c_tok = int(out_data.get("completion_tokens") or estimate_tokens(answer))
    return {
        "model_name": str(out_data.get("model_name") or model_name or "gemini-2.5-flash"),
        "api_key_masked": str(out_data.get("api_key_masked") or key_mask),
        "prompt_tokens": p_tok,
        "completion_tokens": c_tok,
        "total_tokens": p_tok + c_tok,
    }


async def query_agri_rag(
    question: str,
    session_id: Optional[str] = None,
    crop: Optional[str] = None,
    farm: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Call Agri-RAG (/v1/chat on port 8070, or in-process container fallback, or local RAGPipeline in CI)."""
    payload: Dict[str, Any] = {"question": question}
    if session_id:
        payload["session_id"] = session_id
    if crop:
        payload["crop"] = crop
    if farm:
        payload["farm"] = farm

    if not (os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("CI")):
        try:
            r = await asyncio.to_thread(
                ext_requests.post,
                f"{AGRI_RAG_URL}/v1/chat",
                json=payload,
                timeout=25,
            )
            if r.status_code == 200:
                out = r.json()
                out["_llm_telemetry"] = build_rag_llm_telemetry(question, out)
                return out
        except Exception as e:
            logger.warning(f"HTTP Agri-RAG notice ({e}), trying in-process agri-rag...")

        try:
            c = await asyncio.to_thread(get_local_agri_rag)
            from agri_rag.domain.farm import FarmContext
            farm_obj = FarmContext(**farm) if farm else None
            res = await c.pipeline.ask(question, session_id=session_id, farm=farm_obj, crop=crop)
            out = {
                "answer": res.answer,
                "grounded": res.grounded,
                "session_id": res.session_id,
                "sources": res.sources,
                "cited_ids": res.cited_ids,
                "timings": res.timings,
            }
            out["_llm_telemetry"] = build_rag_llm_telemetry(question, out)
            return out
        except Exception as e:
            logger.warning(f"In-process agri-rag notice ({e}), falling back to local RAGPipeline...")

    pipeline = await asyncio.to_thread(get_rag_pipeline)
    rag_res = await asyncio.to_thread(pipeline.run, user_query=question)
    citations = rag_res.get("citations", []) or []
    sources_list = [
        {"id": c.get("citation_tag", f"[{i+1}]"), "title": c.get("source_doc", "مرجع زراعي"), "section": c.get("doc_type", "")}
        for i, c in enumerate(citations)
    ]
    out = {
        "answer": rag_res.get("answer", ""),
        "grounded": rag_res.get("retrieval_confidence", 0.0) >= 0.70,
        "session_id": session_id or "",
        "sources": sources_list,
        "cited_ids": [c.get("citation_tag", "") for c in citations],
        "timings": {"total": rag_res.get("latency_seconds", 0.0)},
    }
    out["_llm_telemetry"] = build_rag_llm_telemetry(question, out)
    return out


KNOWN_AGRI_RAG_CROPS = {"طماطم", "بطاطس", "ذرة", "قمح", "مانجو", "أرز"}

IRRIG_TO_ENUM: Dict[str, str] = {
    "تنقيط": "drip",
    "drip": "drip",
    "غمر": "surface",
    "surface": "surface",
    "رش": "sprinkler",
    "sprinkler": "sprinkler",
}


def format_agri_rag_sources(data: Dict[str, Any]) -> Tuple[List[str], float]:
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

