"""Telemetry Repository: Request Telemetry, Visitor Gating, Token Tracking, and User 360 Dossiers.

Provides:
- Silent visitor logging, page performance, and error traceback storage
- LLM token tracking, Gemini cost estimation, and key rotation metrics
- Guest Usage Gate quota calculation (`get_guest_usage_status`)
- Complete User 360° Activity Dossier (`get_user_360_profile`)
- Full developer analytics & active learning telemetry aggregation (`get_developer_analytics`)
"""

from __future__ import annotations

import datetime
import json
import os
import sqlite3
import traceback
from typing import Any, Dict, Optional

from computer_vision.storage.connection import DB_PATH, init_db
from computer_vision.storage.utils import (
    estimate_gemini_cost_usd,
    estimate_tokens,
    mask_api_key,
    parse_user_agent,
    resolve_ip_geo,
)


def get_guest_usage_status(
    visitor_hash: str,
    client_ip: str = "",
    user_id: Optional[int] = None,
    max_free_uses: int = 3,
    enforce_login: bool = True,
) -> Dict[str, Any]:
    """Check how many free actions (image diagnoses + chat questions) an unauthenticated guest has used."""
    init_db()
    limit_val = max(0, int(3 if max_free_uses is None else max_free_uses))
    try:
        with sqlite3.connect(str(DB_PATH), timeout=10.0) as conn:
            conn.row_factory = sqlite3.Row
            eff_uid = user_id
            eff_uname = ""
            if not eff_uid and visitor_hash:
                vp = conn.execute(
                    "SELECT user_id, user_name FROM visitor_profiles WHERE visitor_id = ?",
                    (visitor_hash,),
                ).fetchone()
                if vp and vp["user_id"]:
                    eff_uid = int(vp["user_id"])
                    eff_uname = vp["user_name"] or ""

            if eff_uid:
                u_chats = conn.execute("SELECT COUNT(*) FROM chat_logs WHERE user_id = ?", (int(eff_uid),)).fetchone()[0]
                u_imgs = conn.execute("SELECT COUNT(*) FROM uploaded_images WHERE user_id = ?", (int(eff_uid),)).fetchone()[0]
                return {
                    "is_authenticated": True,
                    "user_id": int(eff_uid),
                    "user_name": eff_uname,
                    "used_chats": int(u_chats or 0),
                    "used_images": int(u_imgs or 0),
                    "used_total": int((u_chats or 0) + (u_imgs or 0)),
                    "max_free_uses": limit_val,
                    "remaining_free": 999999,
                    "require_login": False,
                    "enforce_login": bool(enforce_login),
                }

            ts_24h = (datetime.datetime.now() - datetime.timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
            if visitor_hash:
                used_chats = conn.execute(
                    "SELECT COUNT(*) FROM chat_logs WHERE visitor_hash = ?",
                    (visitor_hash,),
                ).fetchone()[0]
                used_images = conn.execute(
                    "SELECT COUNT(*) FROM uploaded_images WHERE visitor_hash = ? AND source_endpoint NOT LIKE '%/cv/%'",
                    (visitor_hash,),
                ).fetchone()[0]
            elif client_ip:
                used_chats = conn.execute(
                    "SELECT COUNT(*) FROM chat_logs WHERE client_ip = ? AND created_at >= ? AND (user_id IS NULL OR user_id = 0)",
                    (client_ip, ts_24h),
                ).fetchone()[0]
                used_images = conn.execute(
                    "SELECT COUNT(*) FROM uploaded_images WHERE client_ip = ? AND created_at >= ? AND (user_id IS NULL OR user_id = 0) AND source_endpoint NOT LIKE '%/cv/%'",
                    (client_ip, ts_24h),
                ).fetchone()[0]
            else:
                used_chats, used_images = 0, 0

            used_total = int(used_chats or 0) + int(used_images or 0)
            remaining = max(0, limit_val - used_total)
            require_login = bool(enforce_login and used_total >= limit_val)
            return {
                "is_authenticated": False,
                "user_id": None,
                "user_name": "",
                "used_chats": int(used_chats or 0),
                "used_images": int(used_images or 0),
                "used_total": used_total,
                "max_free_uses": limit_val,
                "remaining_free": remaining,
                "require_login": require_login,
                "enforce_login": bool(enforce_login),
            }
    except Exception:
        return {
            "is_authenticated": bool(user_id),
            "user_id": user_id,
            "user_name": "",
            "used_chats": 0,
            "used_images": 0,
            "used_total": 0,
            "max_free_uses": limit_val,
            "remaining_free": limit_val,
            "require_login": False,
            "enforce_login": bool(enforce_login),
        }


def get_user_360_profile(
    user_id: Optional[int] = None,
    visitor_id: str = "",
    client_ip: str = "",
) -> Dict[str, Any]:
    """Return a comprehensive 360-degree dossier of a user or visitor: identity, features used, tokens, chats, images, and navigation trail."""
    init_db()
    with sqlite3.connect(str(DB_PATH), timeout=10.0) as conn:
        conn.row_factory = sqlite3.Row

        user_dict = None
        visitor_profile = None

        if user_id:
            u_row = conn.execute("SELECT * FROM users WHERE id = ?", (int(user_id),)).fetchone()
            if u_row:
                user_dict = dict(u_row)
                user_dict.pop("password_hash", None)
                if not visitor_id and user_dict.get("last_visitor_id"):
                    visitor_id = user_dict["last_visitor_id"]

        if visitor_id:
            v_row = conn.execute("SELECT * FROM visitor_profiles WHERE visitor_id = ?", (visitor_id,)).fetchone()
            if v_row:
                visitor_profile = dict(v_row)
                if not user_dict and visitor_profile.get("user_id"):
                    u_row2 = conn.execute("SELECT * FROM users WHERE id = ?", (int(visitor_profile["user_id"]),)).fetchone()
                    if u_row2:
                        user_dict = dict(u_row2)
                        user_dict.pop("password_hash", None)

        filter_clauses = []
        filter_params = []
        if user_id:
            filter_clauses.append("user_id = ?")
            filter_params.append(int(user_id))
        if visitor_id:
            filter_clauses.append("visitor_hash = ?")
            filter_params.append(visitor_id)
        if not filter_clauses and client_ip:
            filter_clauses.append("client_ip = ?")
            filter_params.append(client_ip)

        where_cond = " OR ".join(filter_clauses) if filter_clauses else "1=0"

        img_rows = conn.execute(
            f"""
            SELECT id, created_at, filename, source_endpoint, model_used, predicted_class, predicted_class_ar,
                   confidence, user_query, rag_advice, latency_ms, width, height, quality_flag, verified_label
            FROM uploaded_images
            WHERE {where_cond}
            ORDER BY id DESC
            LIMIT 40
            """,
            filter_params,
        ).fetchall()
        images = [dict(r) for r in img_rows]

        chat_rows = conn.execute(
            f"""
            SELECT id, created_at, location, crop, user_query, bot_answer, confidence, latency_ms,
                   topic_category, prompt_tokens, completion_tokens, total_tokens, llm_model
            FROM chat_logs
            WHERE {where_cond}
            ORDER BY id DESC
            LIMIT 50
            """,
            filter_params,
        ).fetchall()
        chats = [dict(r) for r in chat_rows]

        tok_row = conn.execute(
            f"""
            SELECT COUNT(*) AS total_calls,
                   COALESCE(SUM(total_tokens), 0) AS total_tokens,
                   COALESCE(SUM(estimated_cost_usd), 0.0) AS estimated_cost_usd
            FROM llm_token_logs
            WHERE {where_cond}
            """,
            filter_params,
        ).fetchone()

        visit_where = where_cond.replace("visitor_hash", "visitor_hash")
        visit_rows = conn.execute(
            f"""
            SELECT id, created_at, method, path, query_string, referer, status_code, latency_ms
            FROM visitor_logs
            WHERE {visit_where}
            ORDER BY id DESC
            LIMIT 60
            """,
            filter_params,
        ).fetchall()
        visits = [dict(r) for r in visit_rows]

        features_used = set()
        if images:
            features_used.add("📸 فحص أمراض النبات بالذكاء الاصطناعي")
        if chats:
            features_used.add("💬 استشارة المهندس الزراعي (Agri-RAG)")
        paths_seen = {v["path"] for v in visits}
        if any("/weather" in p for p in paths_seen):
            features_used.add("⛅ التنبؤ الجوي وتوصيات الطقس الزراعي")
        if any("/m" in p or "mobile" in p for p in paths_seen):
            features_used.add("📱 تطبيق الموبايل PWA")
        if any("/audio" in p or "/tts" in p or "/stt" in p for p in paths_seen):
            features_used.add("🎙️ الاستشارة الصوتية باللهجة المصرية")

        crops_interested = set()
        if user_dict and user_dict.get("primary_crop"):
            crops_interested.add(user_dict["primary_crop"])
        if visitor_profile and visitor_profile.get("primary_crop"):
            crops_interested.add(visitor_profile["primary_crop"])
        for c in chats:
            if c.get("crop"):
                crops_interested.add(c["crop"])

        return {
            "user": user_dict,
            "visitor_profile": visitor_profile,
            "summary": {
                "images_count": len(images),
                "chats_count": len(chats),
                "visits_count": len(visits),
                "tokens_used": int(tok_row["total_tokens"] or 0) if tok_row else 0,
                "estimated_cost_usd": round(float(tok_row["estimated_cost_usd"] or 0.0), 5) if tok_row else 0.0,
                "features_used": sorted(list(features_used)),
                "crops_interested": sorted(list(crops_interested)),
            },
            "images": images,
            "chats": chats,
            "visits": visits,
        }


def save_token_usage_log(
    service_type: str,
    model_name: str,
    api_key_masked: str = "",
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    latency_ms: float = 0.0,
    status: str = "success",
    endpoint: str = "",
    user_id: Optional[int] = None,
    user_name: str = "",
    visitor_hash: str = "",
    client_ip: str = "",
    request_preview: str = "",
    query_preview: str = "",
    created_at_override: str = "",
) -> int:
    """Record an AI/LLM token & API-key consumption event for developer observability."""
    try:
        init_db()
        now = datetime.datetime.now()
        now_str = created_at_override or now.strftime("%Y-%m-%d %H:%M:%S")
        hour_bucket = now_str[:13] + ":00" if len(now_str) >= 13 else now.strftime("%Y-%m-%d %H:00")

        p_tok = max(0, int(prompt_tokens or 0))
        c_tok = max(0, int(completion_tokens or 0))
        t_tok = max(0, int(total_tokens or (p_tok + c_tok)))
        if t_tok > 0 and p_tok == 0 and c_tok == 0:
            p_tok = int(t_tok * 0.7)
            c_tok = t_tok - p_tok

        cost_usd = estimate_gemini_cost_usd(model_name, p_tok, c_tok) if status != "cache_hit" else 0.0
        clean_key = mask_api_key(api_key_masked) if api_key_masked else "Key #1 (الأساسي)"
        preview_txt = (request_preview or query_preview or "")[:140]

        with sqlite3.connect(str(DB_PATH), timeout=10.0) as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO llm_token_logs (
                    created_at, hour_bucket, service_type, endpoint, model_name,
                    api_key_masked, prompt_tokens, completion_tokens, total_tokens,
                    estimated_cost_usd, latency_ms, status, user_id, user_name,
                    visitor_hash, client_ip, request_preview
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    now_str,
                    hour_bucket,
                    service_type or "Agri-RAG Chat",
                    endpoint or "/api/chat",
                    model_name or "gemini-2.5-flash",
                    clean_key,
                    p_tok,
                    c_tok,
                    t_tok,
                    cost_usd,
                    round(float(latency_ms or 0.0), 2),
                    status or "success",
                    user_id,
                    user_name or "",
                    visitor_hash or "",
                    client_ip or "",
                    preview_txt,
                ),
            )
            conn.commit()
            return int(cur.lastrowid)
    except Exception:
        return 0


def save_visitor_log(
    method: str,
    path: str,
    status_code: int = 200,
    latency_ms: float = 0.0,
    query_string: str = "",
    client_ip: str = "",
    visitor_hash: str = "",
    user_agent: str = "",
    device_type: str = "",
    browser_os: str = "",
    referer: str = "",
    user_id: Optional[int] = None,
    user_name: str = "",
    user_identifier: str = "",
) -> None:
    """Silently record a page visit or API request with Geo-IP, ISP, and authenticated user if present."""
    try:
        init_db()
        now = datetime.datetime.now()
        now_str = now.strftime("%Y-%m-%d %H:%M:%S")
        hour_bucket = now.strftime("%Y-%m-%d %H:00")

        if not device_type and user_agent:
            device_type, browser_os = parse_user_agent(user_agent)

        geo = resolve_ip_geo(client_ip)

        with sqlite3.connect(str(DB_PATH)) as conn:
            conn.row_factory = sqlite3.Row
            if not user_id and visitor_hash:
                vp = conn.execute(
                    "SELECT user_id, user_name, user_identifier FROM visitor_profiles WHERE visitor_id = ?",
                    (visitor_hash,),
                ).fetchone()
                if vp and vp["user_id"]:
                    user_id = vp["user_id"]
                    user_name = vp["user_name"] or ""
                    user_identifier = vp["user_identifier"] or ""

            conn.execute(
                """
                INSERT INTO visitor_logs (
                    created_at, hour_bucket, client_ip, visitor_hash, user_agent,
                    device_type, browser_os, method, path, query_string,
                    referer, status_code, latency_ms, geo_city, isp,
                    user_id, user_name, user_identifier
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    now_str,
                    hour_bucket,
                    client_ip,
                    visitor_hash,
                    user_agent,
                    device_type,
                    browser_os,
                    method,
                    path,
                    query_string,
                    referer,
                    int(status_code),
                    round(float(latency_ms or 0.0), 2),
                    geo["city"],
                    geo["isp"],
                    user_id,
                    user_name or "",
                    user_identifier or "",
                ),
            )
            if visitor_hash:
                vp_row = conn.execute(
                    "SELECT visitor_id FROM visitor_profiles WHERE visitor_id = ?",
                    (visitor_hash,),
                ).fetchone()
                if vp_row:
                    conn.execute(
                        """
                        UPDATE visitor_profiles
                        SET last_seen_at = ?,
                            visit_count = COALESCE(visit_count, 0) + 1,
                            user_id = COALESCE(?, user_id),
                            user_name = CASE WHEN ? != '' THEN ? ELSE user_name END,
                            user_identifier = CASE WHEN ? != '' THEN ? ELSE user_identifier END,
                            last_ip = CASE WHEN ? != '' THEN ? ELSE last_ip END,
                            ip_city = CASE WHEN ? != '' THEN ? ELSE ip_city END,
                            isp = CASE WHEN ? != '' THEN ? ELSE isp END,
                            device_type = CASE WHEN ? != '' THEN ? ELSE device_type END,
                            browser_os = CASE WHEN ? != '' THEN ? ELSE browser_os END
                        WHERE visitor_id = ?
                        """,
                        (
                            now_str,
                            user_id,
                            user_name or "", user_name or "",
                            user_identifier or "", user_identifier or "",
                            client_ip, client_ip,
                            geo["city"], geo["city"],
                            geo["isp"], geo["isp"],
                            device_type, device_type,
                            browser_os, browser_os,
                            visitor_hash,
                        ),
                    )
                else:
                    conn.execute(
                        """
                        INSERT INTO visitor_profiles (
                            visitor_id, first_seen_at, last_seen_at, user_id, user_name, user_identifier,
                            pinned_governorate, location_source, last_ip, ip_city, isp,
                            device_type, browser_os, visit_count
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'ip', ?, ?, ?, ?, ?, 1)
                        """,
                        (
                            visitor_hash, now_str, now_str, user_id, user_name or "", user_identifier or "",
                            geo.get("city", "") or "القاهرة", client_ip, geo.get("city", ""), geo.get("isp", ""),
                            device_type, browser_os,
                        ),
                    )
            conn.commit()
    except Exception:
        pass


def save_error_log(
    endpoint: str,
    error: Exception | str,
    status_code: int = 500,
    client_ip: str = "",
    user_agent: str = "",
    device_type: str = "",
    request_summary: str = "",
) -> None:
    """Silently record an API or model error with full traceback for developer debugging."""
    try:
        init_db()
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(error, Exception):
            error_type = type(error).__name__
            error_message = str(error)
            tb_text = traceback.format_exc()
        else:
            error_type = "Error"
            error_message = str(error)
            tb_text = ""

        if not device_type and user_agent:
            device_type, _ = parse_user_agent(user_agent)

        with sqlite3.connect(str(DB_PATH)) as conn:
            conn.execute(
                """
                INSERT INTO error_logs (
                    created_at, endpoint, client_ip, device_type, user_agent,
                    status_code, error_type, error_message, traceback_text, request_summary
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    now_str,
                    endpoint,
                    client_ip,
                    device_type,
                    user_agent,
                    int(status_code),
                    error_type,
                    error_message,
                    tb_text,
                    request_summary[:1000] if request_summary else "",
                ),
            )
            conn.commit()
    except Exception:
        pass


def get_developer_analytics(limit: int = 100, primary_key_mask: str = "") -> Dict[str, Any]:
    """Return full telemetry, KPIs, Active Learning stats, Knowledge Gaps, Peak Hours, Cookie Profiles, and detailed logs."""
    init_db()
    eff_primary_key = primary_key_mask or "Key #1 (الأساسي)"
    with sqlite3.connect(str(DB_PATH)) as conn:
        conn.row_factory = sqlite3.Row
        if primary_key_mask:
            conn.execute(
                "UPDATE llm_token_logs SET api_key_masked = ? WHERE api_key_masked IN ('Key #1 (الأساسي)', '', 'local-model')",
                (primary_key_mask,),
            )
            conn.execute(
                "UPDATE chat_logs SET api_key_masked = ? WHERE api_key_masked IN ('Key #1 (الأساسي)', '', 'local-model') OR api_key_masked IS NULL",
                (primary_key_mask,),
            )
            conn.commit()

        # 1. Summary KPIs
        total_visits = conn.execute("SELECT COUNT(*) FROM visitor_logs").fetchone()[0]
        unique_ips = conn.execute("SELECT COUNT(DISTINCT client_ip) FROM visitor_logs WHERE client_ip != ''").fetchone()[0]
        unique_visitors = conn.execute("SELECT COUNT(DISTINCT visitor_hash) FROM visitor_logs WHERE visitor_hash != ''").fetchone()[0]
        total_chats = conn.execute("SELECT COUNT(*) FROM chat_logs").fetchone()[0]
        total_images = conn.execute("SELECT COUNT(*) FROM uploaded_images").fetchone()[0]
        total_errors = conn.execute("SELECT COUNT(*) FROM error_logs").fetchone()[0]
        total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]

        uncertain_images = conn.execute("SELECT COUNT(*) FROM uploaded_images WHERE is_uncertain = 1").fetchone()[0]
        verified_images = conn.execute("SELECT COUNT(*) FROM uploaded_images WHERE verified_label != ''").fetchone()[0]
        knowledge_gaps = conn.execute("SELECT COUNT(*) FROM chat_logs WHERE is_knowledge_gap = 1").fetchone()[0]

        avg_chat_ms = conn.execute("SELECT COALESCE(AVG(latency_ms), 0) FROM chat_logs WHERE latency_ms > 0").fetchone()[0]
        avg_img_ms = conn.execute("SELECT COALESCE(AVG(latency_ms), 0) FROM uploaded_images WHERE latency_ms > 0").fetchone()[0]
        avg_visit_ms = conn.execute("SELECT COALESCE(AVG(latency_ms), 0) FROM visitor_logs WHERE latency_ms > 0").fetchone()[0]

        # 1b. Live Traffic Window Metrics (5m, 15m, 1h, 24h) & HTTP Status Breakdown
        now_dt = datetime.datetime.now()
        ts_5m = (now_dt - datetime.timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
        ts_15m = (now_dt - datetime.timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S")
        ts_1h = (now_dt - datetime.timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
        ts_24h = (now_dt - datetime.timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")

        requests_5m = conn.execute("SELECT COUNT(*) FROM visitor_logs WHERE created_at >= ?", (ts_5m,)).fetchone()[0]
        requests_1h = conn.execute("SELECT COUNT(*) FROM visitor_logs WHERE created_at >= ?", (ts_1h,)).fetchone()[0]
        requests_24h = conn.execute("SELECT COUNT(*) FROM visitor_logs WHERE created_at >= ?", (ts_24h,)).fetchone()[0]
        active_visitors_15m = conn.execute("SELECT COUNT(DISTINCT visitor_hash) FROM visitor_logs WHERE created_at >= ? AND visitor_hash != ''", (ts_15m,)).fetchone()[0]
        active_ips_1h = conn.execute("SELECT COUNT(DISTINCT client_ip) FROM visitor_logs WHERE created_at >= ? AND client_ip != ''", (ts_1h,)).fetchone()[0]
        chats_24h = conn.execute("SELECT COUNT(*) FROM chat_logs WHERE created_at >= ?", (ts_24h,)).fetchone()[0]
        images_24h = conn.execute("SELECT COUNT(*) FROM uploaded_images WHERE created_at >= ?", (ts_24h,)).fetchone()[0]

        status_2xx = conn.execute("SELECT COUNT(*) FROM visitor_logs WHERE status_code >= 200 AND status_code < 400").fetchone()[0]
        status_4xx = conn.execute("SELECT COUNT(*) FROM visitor_logs WHERE status_code >= 400 AND status_code < 500").fetchone()[0]
        status_5xx = conn.execute("SELECT COUNT(*) FROM visitor_logs WHERE status_code >= 500").fetchone()[0]

        endpoint_rows = conn.execute(
            """
            SELECT path, COUNT(*) AS hits, ROUND(AVG(latency_ms), 1) AS avg_ms
            FROM visitor_logs
            WHERE path != ''
            GROUP BY path
            ORDER BY hits DESC
            LIMIT 8
            """
        ).fetchall()
        top_endpoints = [dict(r) for r in endpoint_rows]

        # 2. Peak Hours Breakdown
        hourly_rows = conn.execute(
            """
            SELECT substr(created_at, 12, 2) AS hour_of_day, COUNT(*) AS requests_count
            FROM visitor_logs
            WHERE created_at != ''
            GROUP BY hour_of_day
            ORDER BY hour_of_day ASC
            """
        ).fetchall()
        peak_hours = [{"hour": f"{r['hour_of_day']}:00", "count": r["requests_count"]} for r in hourly_rows if r["hour_of_day"]]

        # 3. Top Crops & Topics Asked in Chat
        crop_rows = conn.execute(
            """
            SELECT CASE WHEN crop = '' OR crop IS NULL THEN 'عام / غير محدد' ELSE crop END AS crop_name,
                   COUNT(*) AS cnt
            FROM chat_logs
            GROUP BY crop_name
            ORDER BY cnt DESC
            LIMIT 10
            """
        ).fetchall()
        top_chat_crops = [{"crop": r["crop_name"], "count": r["cnt"]} for r in crop_rows]

        topic_rows = conn.execute(
            """
            SELECT CASE WHEN topic_category = '' OR topic_category IS NULL THEN 'استشارة عامة' ELSE topic_category END AS topic,
                   COUNT(*) AS cnt
            FROM chat_logs
            GROUP BY topic
            ORDER BY cnt DESC
            """
        ).fetchall()
        top_chat_topics = [{"topic": r["topic"], "count": r["cnt"]} for r in topic_rows]

        # 4. Top Diagnosed Plant Diseases
        disease_rows = conn.execute(
            """
            SELECT COALESCE(NULLIF(predicted_class_ar, ''), predicted_class) AS disease_label,
                   COUNT(*) AS cnt
            FROM uploaded_images
            GROUP BY disease_label
            ORDER BY cnt DESC
            LIMIT 10
            """
        ).fetchall()
        top_diseases = [{"disease": r["disease_label"], "count": r["cnt"]} for r in disease_rows]

        # 5. Device Breakdown
        device_rows = conn.execute(
            """
            SELECT CASE WHEN device_type = '' OR device_type IS NULL THEN 'غير معروف' ELSE device_type END AS dev,
                   COUNT(*) AS cnt
            FROM visitor_logs
            GROUP BY dev
            ORDER BY cnt DESC
            """
        ).fetchall()
        devices_breakdown = [{"device": r["dev"], "count": r["cnt"]} for r in device_rows]

        # 6. Top Active Visitor IPs with Geo & ISP
        ip_rows = conn.execute(
            """
            SELECT client_ip, device_type, MAX(geo_city) AS geo_city, MAX(isp) AS isp,
                   COUNT(*) AS hits, MAX(created_at) AS last_seen
            FROM visitor_logs
            WHERE client_ip != ''
            GROUP BY client_ip
            ORDER BY hits DESC
            LIMIT 15
            """
        ).fetchall()
        top_visitors = [dict(r) for r in ip_rows]

        # 7. Registered Users Table
        user_rows = conn.execute(
            """
            SELECT u.id, u.created_at, u.last_login_at, u.full_name, u.identifier,
                   u.phone, u.email, u.governorate, u.primary_crop, u.role,
                   u.login_count, u.client_ip, u.device_type, u.geo_city,
                   u.farm_size_feddan, u.irrigation_type, u.gps_lat, u.gps_lon, u.location_source, u.last_visitor_id,
                   u.auth_provider, u.avatar_url,
                   (SELECT COUNT(*) FROM uploaded_images img WHERE img.user_id = u.id OR (u.last_visitor_id != '' AND img.visitor_hash = u.last_visitor_id)) AS images_count,
                   (SELECT COUNT(*) FROM chat_logs ch WHERE ch.user_id = u.id OR (u.last_visitor_id != '' AND ch.visitor_hash = u.last_visitor_id)) AS chats_count,
                   (SELECT COUNT(*) FROM visitor_logs vl WHERE vl.user_id = u.id OR (u.last_visitor_id != '' AND vl.visitor_hash = u.last_visitor_id)) AS visits_count,
                   (SELECT COALESCE(SUM(total_tokens), 0) FROM llm_token_logs tl WHERE tl.user_id = u.id OR (u.last_visitor_id != '' AND tl.visitor_hash = u.last_visitor_id)) AS tokens_used,
                   (SELECT user_query FROM chat_logs ch2 WHERE ch2.user_id = u.id OR (u.last_visitor_id != '' AND ch2.visitor_hash = u.last_visitor_id) ORDER BY ch2.id DESC LIMIT 1) AS last_question,
                   (SELECT predicted_class_ar FROM uploaded_images im2 WHERE im2.user_id = u.id OR (u.last_visitor_id != '' AND im2.visitor_hash = u.last_visitor_id) ORDER BY im2.id DESC LIMIT 1) AS last_diagnosis
            FROM users u
            ORDER BY u.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        registered_users = []
        for r in user_rows:
            ud = dict(r)
            feats = []
            if int(ud.get("images_count") or 0) > 0:
                feats.append("📸 فحص صور")
            if int(ud.get("chats_count") or 0) > 0:
                feats.append("💬 شات زراعي")
            if int(ud.get("visits_count") or 0) > 2:
                feats.append("⛅ طقس وأدوات")
            ud["features_used"] = feats
            registered_users.append(ud)

        # 7b. Persistent Cookie-Tracked Visitor & User Profiles
        cookie_rows = conn.execute(
            """
            SELECT vp.*,
                   (SELECT COUNT(*) FROM uploaded_images img WHERE img.visitor_hash = vp.visitor_id OR (vp.user_id IS NOT NULL AND img.user_id = vp.user_id)) AS images_count,
                   (SELECT COUNT(*) FROM chat_logs ch WHERE ch.visitor_hash = vp.visitor_id OR (vp.user_id IS NOT NULL AND ch.user_id = vp.user_id)) AS chats_count,
                   (SELECT COALESCE(SUM(total_tokens), 0) FROM llm_token_logs tl WHERE tl.visitor_hash = vp.visitor_id OR (vp.user_id IS NOT NULL AND tl.user_id = vp.user_id)) AS tokens_used,
                   (SELECT user_query FROM chat_logs ch2 WHERE ch2.visitor_hash = vp.visitor_id OR (vp.user_id IS NOT NULL AND ch2.user_id = vp.user_id) ORDER BY ch2.id DESC LIMIT 1) AS last_question,
                   (SELECT predicted_class_ar FROM uploaded_images im2 WHERE im2.visitor_hash = vp.visitor_id OR (vp.user_id IS NOT NULL AND im2.user_id = vp.user_id) ORDER BY im2.id DESC LIMIT 1) AS last_diagnosis
            FROM visitor_profiles vp
            ORDER BY vp.last_seen_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        cookie_profiles = []
        for r in cookie_rows:
            cd = dict(r)
            feats = []
            if int(cd.get("images_count") or 0) > 0:
                feats.append("📸 فحص صور")
            if int(cd.get("chats_count") or 0) > 0:
                feats.append("💬 شات زراعي")
            cd["features_used"] = feats
            cookie_profiles.append(cd)

        # 8. Recent Chat Logs
        chat_rows = conn.execute(
            """
            SELECT id, created_at, client_ip, visitor_hash, device_type, session_id, location, crop,
                   rag_engine, user_query, bot_answer, sources_json, confidence,
                   latency_ms, status, error_message, topic_category, is_knowledge_gap,
                   geo_city, isp, user_id, user_name, user_identifier,
                   prompt_tokens, completion_tokens, total_tokens, api_key_masked, llm_model
            FROM chat_logs
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        recent_chats = []
        for r in chat_rows:
            d = dict(r)
            try:
                d["sources"] = json.loads(d.pop("sources_json", "[]") or "[]")
            except Exception:
                d["sources"] = []
            if not d.get("total_tokens"):
                pt = 520 + estimate_tokens(d.get("user_query", ""))
                ct = estimate_tokens(d.get("bot_answer", ""))
                d["prompt_tokens"] = pt
                d["completion_tokens"] = ct
                d["total_tokens"] = pt + ct
            if not d.get("llm_model"):
                d["llm_model"] = "gemini-2.5-flash" if "Legacy" not in (d.get("rag_engine") or "") else "Legacy-RAG"
            if not d.get("api_key_masked") or d.get("api_key_masked") == "Key #1 (الأساسي)":
                d["api_key_masked"] = eff_primary_key
            recent_chats.append(d)

        # 8b. Auto-backfill llm_token_logs from historical chats & image diagnoses on first run
        tok_count_row = conn.execute("SELECT COUNT(*) FROM llm_token_logs").fetchone()
        if not tok_count_row or int(tok_count_row[0] or 0) == 0:
            hist_chats = conn.execute(
                "SELECT created_at, hour_bucket, rag_engine, user_query, bot_answer, latency_ms, status, user_id, user_name, visitor_hash, client_ip, prompt_tokens, completion_tokens, total_tokens, api_key_masked, llm_model FROM chat_logs ORDER BY id ASC"
            ).fetchall()
            for hc in hist_chats:
                pt = int(hc["prompt_tokens"] or 0) or (520 + estimate_tokens(hc["user_query"] or ""))
                ct = int(hc["completion_tokens"] or 0) or estimate_tokens(hc["bot_answer"] or "")
                tt = int(hc["total_tokens"] or 0) or (pt + ct)
                m_name = hc["llm_model"] or ("gemini-2.5-flash" if "Legacy" not in (hc["rag_engine"] or "") else "Legacy-RAG")
                k_mask = hc["api_key_masked"] if (hc["api_key_masked"] and hc["api_key_masked"] != "Key #1 (الأساسي)") else eff_primary_key
                cost_val = estimate_gemini_cost_usd(m_name, pt, ct)
                conn.execute(
                    """
                    INSERT INTO llm_token_logs (
                        created_at, hour_bucket, service_type, endpoint, model_name,
                        api_key_masked, prompt_tokens, completion_tokens, total_tokens,
                        estimated_cost_usd, latency_ms, status, user_id, user_name,
                        visitor_hash, client_ip, request_preview
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        hc["created_at"], hc["hour_bucket"] or (hc["created_at"][:13] + ":00"),
                        "استشارة الشات (Agri-RAG)", "/api/chat", m_name, k_mask,
                        pt, ct, tt, cost_val, hc["latency_ms"] or 0.0, hc["status"] or "success",
                        hc["user_id"], hc["user_name"] or "", hc["visitor_hash"] or "",
                        hc["client_ip"] or "", (hc["user_query"] or "")[:140],
                    ),
                )

            hist_imgs = conn.execute(
                "SELECT created_at, source_endpoint, model_used, predicted_class_ar, user_query, rag_advice, latency_ms, user_id, user_name, visitor_hash, client_ip FROM uploaded_images ORDER BY id ASC"
            ).fetchall()
            for hi in hist_imgs:
                hr_b = (hi["created_at"] or "")[:13] + ":00"
                gate_pt, gate_ct = 295, 12
                conn.execute(
                    """
                    INSERT INTO llm_token_logs (
                        created_at, hour_bucket, service_type, endpoint, model_name,
                        api_key_masked, prompt_tokens, completion_tokens, total_tokens,
                        estimated_cost_usd, latency_ms, status, user_id, user_name,
                        visitor_hash, client_ip, request_preview
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        hi["created_at"], hr_b, "فلتر النبات الذكي (Vision Gatekeeper)",
                        hi["source_endpoint"] or "/api/diagnose", "gemini-2.5-flash", eff_primary_key,
                        gate_pt, gate_ct, gate_pt + gate_ct,
                        estimate_gemini_cost_usd("gemini-2.5-flash", gate_pt, gate_ct),
                        round(float(hi["latency_ms"] or 400.0) * 0.28, 1), "success",
                        hi["user_id"], hi["user_name"] or "", hi["visitor_hash"] or "",
                        hi["client_ip"] or "", f"فحص صورة: {hi['predicted_class_ar'] or ''}"[:140],
                    ),
                )
                if hi["rag_advice"] and len(str(hi["rag_advice"])) > 40 and "/cv/predict" not in (hi["source_endpoint"] or ""):
                    rag_pt = 560 + estimate_tokens(hi["user_query"] or "")
                    rag_ct = estimate_tokens(hi["rag_advice"] or "")
                    rag_tt = rag_pt + rag_ct
                    conn.execute(
                        """
                        INSERT INTO llm_token_logs (
                            created_at, hour_bucket, service_type, endpoint, model_name,
                            api_key_masked, prompt_tokens, completion_tokens, total_tokens,
                            estimated_cost_usd, latency_ms, status, user_id, user_name,
                            visitor_hash, client_ip, request_preview
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            hi["created_at"], hr_b, "روشتة تشخيص الصورة (Agri-RAG)",
                            hi["source_endpoint"] or "/api/diagnose", "gemini-2.5-flash", eff_primary_key,
                            rag_pt, rag_ct, rag_tt,
                            estimate_gemini_cost_usd("gemini-2.5-flash", rag_pt, rag_ct),
                            round(float(hi["latency_ms"] or 1200.0) * 0.72, 1), "success",
                            hi["user_id"], hi["user_name"] or "", hi["visitor_hash"] or "",
                            hi["client_ip"] or "", f"روشتة علاج: {hi['predicted_class_ar'] or ''}"[:140],
                        ),
                    )
            conn.commit()

        # 8c. Query Token, Model & API Key Analytics
        tok_summary_row = conn.execute(
            """
            SELECT COUNT(*) AS total_calls,
                   COALESCE(SUM(prompt_tokens), 0) AS prompt_tokens,
                   COALESCE(SUM(completion_tokens), 0) AS completion_tokens,
                   COALESCE(SUM(total_tokens), 0) AS total_tokens,
                   COALESCE(SUM(estimated_cost_usd), 0.0) AS total_cost_usd,
                   COALESCE(AVG(latency_ms), 0.0) AS avg_latency_ms,
                   COALESCE(SUM(CASE WHEN status = 'cache_hit' THEN 1 ELSE 0 END), 0) AS cache_hits,
                   COALESCE(SUM(CASE WHEN status = 'cache_hit' THEN total_tokens ELSE 0 END), 0) AS tokens_saved_by_cache,
                   COALESCE(SUM(CASE WHEN status LIKE '%429%' OR status = 'rate_limited' THEN 1 ELSE 0 END), 0) AS rate_limit_429_count
            FROM llm_token_logs
            """
        ).fetchone()

        tok_24h_row = conn.execute(
            """
            SELECT COUNT(*) AS calls_24h,
                   COALESCE(SUM(total_tokens), 0) AS tokens_24h,
                   COALESCE(SUM(estimated_cost_usd), 0.0) AS cost_24h_usd
            FROM llm_token_logs
            WHERE created_at >= ?
            """,
            (ts_24h,),
        ).fetchone()

        by_model_rows = conn.execute(
            """
            SELECT model_name,
                   COUNT(*) AS calls,
                   COALESCE(SUM(prompt_tokens), 0) AS prompt_tokens,
                   COALESCE(SUM(completion_tokens), 0) AS completion_tokens,
                   COALESCE(SUM(total_tokens), 0) AS total_tokens,
                   ROUND(COALESCE(SUM(estimated_cost_usd), 0.0), 5) AS cost_usd,
                   ROUND(COALESCE(AVG(latency_ms), 0.0), 1) AS avg_ms,
                   COALESCE(SUM(CASE WHEN status = 'success' OR status = 'cache_hit' THEN 1 ELSE 0 END), 0) AS ok_calls,
                   COALESCE(SUM(CASE WHEN status NOT IN ('success', 'cache_hit') THEN 1 ELSE 0 END), 0) AS err_calls
            FROM llm_token_logs
            GROUP BY model_name
            ORDER BY total_tokens DESC
            """
        ).fetchall()
        tokens_by_model = []
        for r in by_model_rows:
            md = dict(r)
            md["model"] = md.get("model_name") or "gemini-2.5-flash"
            tokens_by_model.append(md)

        by_key_rows = conn.execute(
            """
            SELECT api_key_masked,
                   COUNT(*) AS calls,
                   COALESCE(SUM(CASE WHEN created_at >= ? THEN 1 ELSE 0 END), 0) AS calls_24h,
                   COALESCE(SUM(prompt_tokens), 0) AS prompt_tokens,
                   COALESCE(SUM(completion_tokens), 0) AS completion_tokens,
                   COALESCE(SUM(total_tokens), 0) AS total_tokens,
                   COALESCE(SUM(CASE WHEN created_at >= ? THEN total_tokens ELSE 0 END), 0) AS tokens_24h,
                   ROUND(COALESCE(SUM(estimated_cost_usd), 0.0), 5) AS cost_usd,
                   ROUND(COALESCE(AVG(latency_ms), 0.0), 1) AS avg_ms,
                   COALESCE(SUM(CASE WHEN status LIKE '%429%' OR status = 'rate_limited' THEN 1 ELSE 0 END), 0) AS errors_429,
                   COALESCE(SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END), 0) AS errors_other,
                   MAX(created_at) AS last_used
            FROM llm_token_logs
            GROUP BY api_key_masked
            ORDER BY total_tokens DESC
            """,
            (ts_24h, ts_24h),
        ).fetchall()
        tokens_by_key = []
        for r in by_key_rows:
            kd = dict(r)
            kd["api_key"] = kd.get("api_key_masked") or eff_primary_key
            kd["daily_quota_limit"] = 1500
            kd["daily_quota_pct"] = round(min(100.0, (float(kd.get("calls_24h") or 0) / 1500.0) * 100.0), 1)
            tokens_by_key.append(kd)

        by_service_rows = conn.execute(
            """
            SELECT service_type,
                   COUNT(*) AS calls,
                   COALESCE(SUM(prompt_tokens), 0) AS prompt_tokens,
                   COALESCE(SUM(completion_tokens), 0) AS completion_tokens,
                   COALESCE(SUM(total_tokens), 0) AS total_tokens,
                   ROUND(COALESCE(SUM(estimated_cost_usd), 0.0), 5) AS cost_usd,
                   ROUND(COALESCE(AVG(latency_ms), 0.0), 1) AS avg_ms
            FROM llm_token_logs
            GROUP BY service_type
            ORDER BY total_tokens DESC
            """
        ).fetchall()
        tokens_by_service = []
        for r in by_service_rows:
            sd = dict(r)
            sd["service"] = sd.get("service_type") or "Agri-RAG"
            tokens_by_service.append(sd)

        recent_tok_rows = conn.execute(
            """
            SELECT id, created_at, service_type, endpoint, model_name, api_key_masked,
                   prompt_tokens, completion_tokens, total_tokens, estimated_cost_usd,
                   latency_ms, status, user_id, user_name, visitor_hash, client_ip, request_preview
            FROM llm_token_logs
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        recent_token_logs = []
        for r in recent_tok_rows:
            td = dict(r)
            td["query_preview"] = td.get("request_preview") or ""
            recent_token_logs.append(td)

        total_tok_calls = int(tok_summary_row["total_calls"] or 0) if tok_summary_row else 0
        total_tok_sum = int(tok_summary_row["total_tokens"] or 0) if tok_summary_row else 0
        saved_tok = int(tok_summary_row["tokens_saved_by_cache"] or 0) if tok_summary_row else 0

        token_analytics = {
            "summary": {
                "total_calls": total_tok_calls,
                "prompt_tokens": int(tok_summary_row["prompt_tokens"] or 0) if tok_summary_row else 0,
                "completion_tokens": int(tok_summary_row["completion_tokens"] or 0) if tok_summary_row else 0,
                "total_tokens": total_tok_sum,
                "avg_tokens_per_call": round(total_tok_sum / max(1, total_tok_calls), 1),
                "estimated_cost_usd": round(float(tok_summary_row["total_cost_usd"] or 0.0), 4) if tok_summary_row else 0.0,
                "avg_latency_ms": round(float(tok_summary_row["avg_latency_ms"] or 0.0), 1) if tok_summary_row else 0.0,
                "cache_hits": int(tok_summary_row["cache_hits"] or 0) if tok_summary_row else 0,
                "tokens_saved_by_cache": saved_tok,
                "cached_tokens_saved": saved_tok,
                "rate_limit_429_count": int(tok_summary_row["rate_limit_429_count"] or 0) if tok_summary_row else 0,
                "calls_24h": int(tok_24h_row["calls_24h"] or 0) if tok_24h_row else 0,
                "tokens_24h": int(tok_24h_row["tokens_24h"] or 0) if tok_24h_row else 0,
                "cost_24h_usd": round(float(tok_24h_row["cost_24h_usd"] or 0.0), 4) if tok_24h_row else 0.0,
            },
            "by_model": tokens_by_model,
            "by_api_key": tokens_by_key,
            "by_service": tokens_by_service,
            "recent_logs": recent_token_logs,
        }

        # 9. Recent Uploaded Images
        img_rows = conn.execute(
            """
            SELECT id, created_at, filename, content_type, file_path, sha256_hash,
                   source_endpoint, model_used, predicted_class, predicted_class_ar,
                   confidence, top_predictions_json, user_query, rag_advice,
                   client_ip, visitor_hash, device_type, latency_ms, width, height, file_size_kb,
                   blur_score, brightness_score, green_ratio, quality_flag,
                   exif_camera, margin_score, is_uncertain, verified_label,
                   developer_notes, geo_city, isp, weather_snapshot,
                   user_id, user_name, user_identifier
            FROM uploaded_images
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        recent_images = []
        for r in img_rows:
            d = dict(r)
            try:
                d["top_predictions"] = json.loads(d.pop("top_predictions_json", "[]") or "[]")
            except Exception:
                d["top_predictions"] = []
            recent_images.append(d)

        # 10. Recent Visitor Traffic Logs
        visit_rows = conn.execute(
            """
            SELECT id, created_at, client_ip, visitor_hash, device_type, browser_os,
                   method, path, query_string, referer, status_code, latency_ms,
                   geo_city, isp, user_id, user_name, user_identifier
            FROM visitor_logs
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        recent_visits = [dict(r) for r in visit_rows]

        # 11. Recent Error Logs
        err_rows = conn.execute(
            """
            SELECT id, created_at, endpoint, client_ip, device_type, status_code,
                   error_type, error_message, traceback_text, request_summary
            FROM error_logs
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        recent_errors = [dict(r) for r in err_rows]

    return {
        "kpis": {
            "total_visits": total_visits,
            "unique_ips": unique_ips,
            "unique_visitors": unique_visitors,
            "total_chats": total_chats,
            "total_images": total_images,
            "total_errors": total_errors,
            "total_users": total_users,
            "uncertain_images": uncertain_images,
            "verified_images": verified_images,
            "knowledge_gaps": knowledge_gaps,
            "avg_chat_latency_ms": round(float(avg_chat_ms or 0.0), 1),
            "avg_image_latency_ms": round(float(avg_img_ms or 0.0), 1),
            "avg_visit_latency_ms": round(float(avg_visit_ms or 0.0), 1),
        },
        "traffic_summary": {
            "requests_5m": requests_5m,
            "requests_1h": requests_1h,
            "requests_24h": requests_24h,
            "rpm_5m": round(float(requests_5m) / 5.0, 2),
            "active_visitors_15m": active_visitors_15m,
            "active_ips_1h": active_ips_1h,
            "chats_24h": chats_24h,
            "images_24h": images_24h,
            "status_2xx": status_2xx,
            "status_4xx": status_4xx,
            "status_5xx": status_5xx,
            "db_size_mb": round(os.path.getsize(DB_PATH) / (1024 * 1024), 2) if os.path.exists(DB_PATH) else 0.0,
        },
        "token_analytics": token_analytics,
        "top_endpoints": top_endpoints,
        "peak_hours": peak_hours,
        "top_chat_crops": top_chat_crops,
        "top_chat_topics": top_chat_topics,
        "top_diseases": top_diseases,
        "devices_breakdown": devices_breakdown,
        "top_visitors": top_visitors,
        "registered_users": registered_users,
        "cookie_profiles": cookie_profiles,
        "recent_chats": recent_chats,
        "recent_images": recent_images,
        "recent_visits": recent_visits,
        "recent_errors": recent_errors,
    }
