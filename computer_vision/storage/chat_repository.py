"""Chat Repository: Agricultural Consultations, Agent Memory, and RAG Fine-Tuning.

Stores chat questions and grounded agronomic answers, extracts past conversation turns
and image diagnosis history for conversational continuity, and formats training data as JSONL.
"""

from __future__ import annotations

import datetime
import json
import sqlite3
from typing import Any, Dict, List, Optional

from computer_vision.storage.connection import DB_PATH, init_db
from computer_vision.storage.utils import (
    classify_chat_topic_and_gap,
    estimate_tokens,
    mask_api_key,
    parse_user_agent,
    resolve_ip_geo,
)


def get_agent_memory_context(
    session_id: str = "",
    user_id: Optional[int] = None,
    visitor_hash: str = "",
    max_turns: int = 12,
) -> Dict[str, Any]:
    """Retrieve persistent conversation history, recent leaf image diagnoses, and farmer profile for the Chat Agent."""
    init_db()
    out: Dict[str, Any] = {
        "farmer_name": None,
        "governorate": None,
        "primary_crop": None,
        "farm_size_feddan": None,
        "irrigation_type": None,
        "diagnoses": [],
        "recent_turns": [],
        "memory_notes": "",
    }
    try:
        with sqlite3.connect(str(DB_PATH), timeout=10.0) as conn:
            conn.row_factory = sqlite3.Row

            # 1. Farmer profile if authenticated
            if user_id:
                u_row = conn.execute(
                    "SELECT full_name, governorate, primary_crop, farm_size_feddan, irrigation_type FROM users WHERE id = ?",
                    (int(user_id),),
                ).fetchone()
                if u_row:
                    out["farmer_name"] = u_row["full_name"]
                    out["governorate"] = u_row["governorate"]
                    out["primary_crop"] = u_row["primary_crop"]
                    out["farm_size_feddan"] = float(u_row["farm_size_feddan"] or 1.0)
                    out["irrigation_type"] = u_row["irrigation_type"] or "غمر"

            # 2. Recent leaf image diagnoses for this user or visitor
            img_rows = []
            if user_id:
                img_rows = conn.execute(
                    """
                    SELECT created_at, predicted_class, predicted_class_ar, confidence, rag_advice
                    FROM uploaded_images
                    WHERE user_id = ?
                    ORDER BY id DESC
                    LIMIT 3
                    """,
                    (int(user_id),),
                ).fetchall()
            elif visitor_hash:
                img_rows = conn.execute(
                    """
                    SELECT created_at, predicted_class, predicted_class_ar, confidence, rag_advice
                    FROM uploaded_images
                    WHERE visitor_hash = ?
                    ORDER BY id DESC
                    LIMIT 2
                    """,
                    (visitor_hash,),
                ).fetchall()

            diag_list = []
            diag_lines = []
            for r in img_rows:
                pred_ar = r["predicted_class_ar"] or r["predicted_class"]
                conf_raw = str(r["confidence"] or "90%").replace("%", "").strip()
                try:
                    conf_float = min(1.0, max(0.0, float(conf_raw) / 100.0))
                except Exception:
                    conf_float = 0.9
                diag_list.append({
                    "label": f"{pred_ar} ({r['predicted_class']})" if r["predicted_class_ar"] else r["predicted_class"],
                    "confidence": round(conf_float, 4),
                })
                diag_lines.append(f"  • صورة بتاريخ {r['created_at']}: التشخيص = {pred_ar} (ثقة {r['confidence']})")
            out["diagnoses"] = diag_list

            # 3. Recent conversation turns from chat_logs
            chat_rows = []
            if session_id:
                chat_rows = conn.execute(
                    """
                    SELECT created_at, location, crop, user_query, bot_answer, sources_json
                    FROM chat_logs
                    WHERE session_id = ? AND status = 'success' AND bot_answer != ''
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (session_id, max_turns),
                ).fetchall()

            if len(chat_rows) < 4 and user_id:
                user_chats = conn.execute(
                    """
                    SELECT created_at, location, crop, user_query, bot_answer, sources_json
                    FROM chat_logs
                    WHERE user_id = ? AND status = 'success' AND bot_answer != ''
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (int(user_id), max_turns),
                ).fetchall()
                seen_q = {(r["user_query"], r["created_at"]) for r in chat_rows}
                for r in user_chats:
                    if (r["user_query"], r["created_at"]) not in seen_q:
                        chat_rows.append(r)
                chat_rows = chat_rows[:max_turns]

            elif not chat_rows and visitor_hash:
                chat_rows = conn.execute(
                    """
                    SELECT created_at, location, crop, user_query, bot_answer, sources_json
                    FROM chat_logs
                    WHERE visitor_hash = ? AND status = 'success' AND bot_answer != ''
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (visitor_hash, min(6, max_turns)),
                ).fetchall()

            chat_rows_chrono = list(reversed(chat_rows))
            turns = []
            turn_lines = []
            for r in chat_rows_chrono:
                try:
                    srcs = json.loads(r["sources_json"] or "[]")
                except Exception:
                    srcs = []
                turns.append({
                    "created_at": r["created_at"],
                    "location": r["location"],
                    "crop": r["crop"],
                    "user_query": r["user_query"],
                    "bot_answer": r["bot_answer"],
                    "sources": srcs,
                })
                if r["crop"] and not out["primary_crop"]:
                    out["primary_crop"] = r["crop"]
                q_short = (r["user_query"] or "").strip()[:220]
                a_short = (r["bot_answer"] or "").strip()[:280]
                turn_lines.append(f"  • سأل المزارع: «{q_short}» ← رديت عليه: «{a_short}»")

            out["recent_turns"] = turns
            out["turns"] = turns
            out["crop"] = out["primary_crop"]

            notes_parts = []
            if diag_lines:
                notes_parts.append("آخر تشخيصات الصور المرفوعة من المزارع:\n" + "\n".join(diag_lines))
            if turn_lines:
                notes_parts.append("سجل المحادثة السابقة مع المزارع (لتكمل عليها):\n" + "\n".join(turn_lines[-8:]))
            out["memory_notes"] = "\n".join(notes_parts)
    except Exception:
        pass
    return out


def save_chat_log(
    user_query: str,
    bot_answer: str = "",
    sources: Optional[List[str]] = None,
    confidence: float = 0.0,
    latency_ms: float = 0.0,
    session_id: str = "",
    location: str = "",
    crop: str = "",
    rag_engine: str = "agri_rag",
    client_ip: str = "",
    user_agent: str = "",
    device_type: str = "",
    visitor_hash: str = "",
    status: str = "success",
    error_message: str = "",
    user_id: Optional[int] = None,
    user_name: str = "",
    user_identifier: str = "",
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    api_key_masked: str = "",
    llm_model: str = "",
) -> int:
    """Silently record a user chat question, RAG answer, topic classification, knowledge-gap signal, token consumption, and geo metadata."""
    init_db()
    now = datetime.datetime.now()
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")
    hour_bucket = now.strftime("%Y-%m-%d %H:00")

    if not device_type and user_agent:
        device_type, _ = parse_user_agent(user_agent)

    topic_cat, is_gap = classify_chat_topic_and_gap(user_query, bot_answer, confidence)
    geo = resolve_ip_geo(client_ip)

    p_tok = int(prompt_tokens or 0)
    c_tok = int(completion_tokens or 0)
    if p_tok <= 0:
        p_tok = 520 + estimate_tokens(user_query)
    if c_tok <= 0 and bot_answer:
        c_tok = estimate_tokens(bot_answer)
    t_tok = int(total_tokens or (p_tok + c_tok))
    eff_model = llm_model or ("gemini-2.5-flash" if "Legacy" not in (rag_engine or "") else "Legacy-RAG")
    eff_key = mask_api_key(api_key_masked) if api_key_masked else "Key #1 (الأساسي)"

    with sqlite3.connect(str(DB_PATH)) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO chat_logs (
                created_at, hour_bucket, client_ip, visitor_hash, user_agent, device_type,
                session_id, location, crop, rag_engine, user_query, bot_answer,
                sources_json, confidence, latency_ms, status, error_message,
                topic_category, is_knowledge_gap, geo_city, isp,
                user_id, user_name, user_identifier,
                prompt_tokens, completion_tokens, total_tokens, api_key_masked, llm_model
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                now_str,
                hour_bucket,
                client_ip,
                visitor_hash,
                user_agent,
                device_type,
                session_id or "",
                location or "",
                crop or "",
                rag_engine or "agri_rag",
                user_query,
                bot_answer,
                json.dumps(sources or [], ensure_ascii=False),
                round(float(confidence or 0.0), 4),
                round(float(latency_ms or 0.0), 2),
                status,
                error_message or "",
                topic_cat,
                is_gap,
                geo["city"],
                geo["isp"],
                user_id,
                user_name or "",
                user_identifier or "",
                p_tok,
                c_tok,
                t_tok,
                eff_key,
                eff_model,
            ),
        )
        conn.commit()
        chat_id = int(cursor.lastrowid)

    from computer_vision.storage.telemetry_repository import save_token_usage_log
    save_token_usage_log(
        service_type="استشارة الشات (Agri-RAG)",
        model_name=eff_model,
        api_key_masked=eff_key,
        prompt_tokens=p_tok,
        completion_tokens=c_tok,
        total_tokens=t_tok,
        latency_ms=latency_ms,
        status=status,
        endpoint="/api/chat",
        user_id=user_id,
        user_name=user_name,
        visitor_hash=visitor_hash,
        client_ip=client_ip,
        request_preview=user_query,
        created_at_override=now_str,
    )
    return chat_id


def build_rag_finetuning_jsonl() -> bytes:
    """Export all successful chat Q&A pairs as OpenAI/Gemini Fine-Tuning JSONL."""
    init_db()
    lines: List[str] = []
    system_prompt = "أنت خبير ومهندس زراعي مصري متخصص. قدم توصيات علمية وعملية دقيقة للمزارع باللهجة المصرية المبسطة."

    with sqlite3.connect(str(DB_PATH)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM chat_logs WHERE status = 'success' AND bot_answer != '' ORDER BY id DESC"
        ).fetchall()
        for r in rows:
            record = {
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": r["user_query"]},
                    {"role": "assistant", "content": r["bot_answer"]},
                ],
                "metadata": {
                    "id": r["id"],
                    "crop": r["crop"],
                    "location": r["location"],
                    "topic": r["topic_category"],
                    "confidence": r["confidence"],
                    "is_knowledge_gap": bool(r["is_knowledge_gap"]),
                },
            }
            lines.append(json.dumps(record, ensure_ascii=False))

    return ("\n".join(lines) + "\n").encode("utf-8")
