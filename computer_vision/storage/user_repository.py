"""User Repository: User Entity Persistence, Credentials, Preferences, and Auth Sessions.

Handles farmer registration, password authentication, social & one-tap logins,
profile management, visitor-to-user linking, and user history retrieval.
"""

from __future__ import annotations

import datetime
import re
import secrets
import sqlite3
from typing import Any, Dict, Optional, Tuple

from computer_vision.storage.connection import DB_PATH, init_db
from computer_vision.storage.utils import (
    VALID_CROPS,
    VALID_EGYPT_GOVERNORATES,
    hash_password,
    normalize_identifier,
    resolve_ip_geo,
    validate_new_user_data,
    verify_password,
)


def link_visitor_to_user(visitor_id: str, user_dict: Dict[str, Any]) -> None:
    """Link a persistent browser cookie (visitor_id) to a registered user account and retroactively attribute past logs."""
    if not visitor_id or not user_dict or not user_dict.get("id"):
        return
    init_db()
    uid = int(user_dict["id"])
    uname = user_dict.get("full_name", "")
    uident = user_dict.get("identifier", "")
    ugov = user_dict.get("governorate", "")
    ucrop = user_dict.get("primary_crop", "")
    uarea = float(user_dict.get("farm_size_feddan") or 1.0)
    uirrig = user_dict.get("irrigation_type") or "غمر"
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        with sqlite3.connect(str(DB_PATH), timeout=10.0) as conn:
            conn.execute("UPDATE users SET last_visitor_id = ? WHERE id = ?", (visitor_id, uid))
            existing = conn.execute(
                "SELECT visitor_id, pinned_governorate, location_source FROM visitor_profiles WHERE visitor_id = ?",
                (visitor_id,),
            ).fetchone()
            if existing:
                conn.execute(
                    """
                    UPDATE visitor_profiles
                    SET last_seen_at = ?,
                        user_id = ?,
                        user_name = ?,
                        user_identifier = ?,
                        pinned_governorate = CASE WHEN pinned_governorate = '' OR location_source = 'ip' THEN ? ELSE pinned_governorate END,
                        location_source = CASE WHEN location_source = 'ip' AND ? != '' THEN 'user_profile' ELSE location_source END,
                        primary_crop = CASE WHEN primary_crop = '' THEN ? ELSE primary_crop END,
                        farm_size_feddan = COALESCE(farm_size_feddan, ?),
                        irrigation_type = COALESCE(NULLIF(irrigation_type, ''), ?)
                    WHERE visitor_id = ?
                    """,
                    (now_str, uid, uname, uident, ugov, ugov, ucrop, uarea, uirrig, visitor_id),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO visitor_profiles (
                        visitor_id, first_seen_at, last_seen_at, user_id, user_name, user_identifier,
                        pinned_governorate, location_source, primary_crop, farm_size_feddan, irrigation_type
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'user_profile', ?, ?, ?)
                    """,
                    (visitor_id, now_str, now_str, uid, uname, uident, ugov, ucrop, uarea, uirrig),
                )
            # Retroactively link anonymous logs from this cookie to the user account so Developer Dashboard correlates them
            conn.execute(
                "UPDATE uploaded_images SET user_id = ?, user_name = ?, user_identifier = ? WHERE visitor_hash = ? AND (user_id IS NULL OR user_id = 0)",
                (uid, uname, uident, visitor_id),
            )
            conn.execute(
                "UPDATE chat_logs SET user_id = ?, user_name = ?, user_identifier = ? WHERE visitor_hash = ? AND (user_id IS NULL OR user_id = 0)",
                (uid, uname, uident, visitor_id),
            )
            conn.execute(
                "UPDATE visitor_logs SET user_id = ?, user_name = ?, user_identifier = ? WHERE visitor_hash = ? AND (user_id IS NULL OR user_id = 0)",
                (uid, uname, uident, visitor_id),
            )
            conn.execute(
                "UPDATE llm_token_logs SET user_id = ?, user_name = ? WHERE visitor_hash = ? AND (user_id IS NULL OR user_id = 0)",
                (uid, uname, visitor_id),
            )
            conn.commit()
    except Exception:
        pass


def save_pinned_location_and_prefs(
    visitor_id: str,
    user_id: Optional[int] = None,
    governorate: Optional[str] = None,
    gps_lat: Optional[float] = None,
    gps_lon: Optional[float] = None,
    location_source: str = "manual",
    primary_crop: Optional[str] = None,
    farm_size_feddan: Optional[float] = None,
    irrigation_type: Optional[str] = None,
    client_ip: str = "",
    device_type: str = "",
    browser_os: str = "",
) -> Dict[str, Any]:
    """Persistently save the user's or visitor's true location (GPS or manual selection) so IP changes never reset it."""
    init_db()
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    geo = resolve_ip_geo(client_ip) if client_ip else {"city": "", "isp": ""}
    gov_clean = (governorate or "").strip()
    if gov_clean and gov_clean not in VALID_EGYPT_GOVERNORATES:
        gov_clean = ""

    with sqlite3.connect(str(DB_PATH), timeout=10.0) as conn:
        conn.row_factory = sqlite3.Row
        if user_id:
            u_row = conn.execute("SELECT * FROM users WHERE id = ?", (int(user_id),)).fetchone()
            if u_row:
                new_gov = gov_clean or u_row["governorate"] or "القاهرة"
                new_lat = gps_lat if gps_lat is not None else u_row["gps_lat"]
                new_lon = gps_lon if gps_lon is not None else u_row["gps_lon"]
                new_src = location_source if (gov_clean or gps_lat is not None) else (u_row["location_source"] or "manual")
                new_crop = primary_crop if primary_crop is not None else (u_row["primary_crop"] or "")
                new_area = float(farm_size_feddan) if farm_size_feddan is not None else float(u_row["farm_size_feddan"] or 1.0)
                new_irrig = irrigation_type if irrigation_type is not None else (u_row["irrigation_type"] or "غمر")
                conn.execute(
                    """
                    UPDATE users
                    SET governorate = ?, gps_lat = ?, gps_lon = ?, location_source = ?,
                        primary_crop = ?, farm_size_feddan = ?, irrigation_type = ?,
                        last_visitor_id = CASE WHEN ? != '' THEN ? ELSE last_visitor_id END
                    WHERE id = ?
                    """,
                    (new_gov, new_lat, new_lon, new_src, new_crop, new_area, new_irrig, visitor_id, visitor_id, int(user_id)),
                )

        if visitor_id:
            v_row = conn.execute("SELECT * FROM visitor_profiles WHERE visitor_id = ?", (visitor_id,)).fetchone()
            if v_row:
                new_gov = gov_clean or v_row["pinned_governorate"] or "القاهرة"
                new_lat = gps_lat if gps_lat is not None else v_row["gps_lat"]
                new_lon = gps_lon if gps_lon is not None else v_row["gps_lon"]
                new_src = location_source if (gov_clean or gps_lat is not None) else (v_row["location_source"] or "manual")
                new_crop = primary_crop if primary_crop is not None else (v_row["primary_crop"] or "")
                new_area = float(farm_size_feddan) if farm_size_feddan is not None else float(v_row["farm_size_feddan"] or 1.0)
                new_irrig = irrigation_type if irrigation_type is not None else (v_row["irrigation_type"] or "غمر")
                conn.execute(
                    """
                    UPDATE visitor_profiles
                    SET last_seen_at = ?,
                        pinned_governorate = ?,
                        gps_lat = ?,
                        gps_lon = ?,
                        location_source = ?,
                        primary_crop = ?,
                        farm_size_feddan = ?,
                        irrigation_type = ?,
                        last_ip = CASE WHEN ? != '' THEN ? ELSE last_ip END,
                        ip_city = CASE WHEN ? != '' THEN ? ELSE ip_city END,
                        isp = CASE WHEN ? != '' THEN ? ELSE isp END
                    WHERE visitor_id = ?
                    """,
                    (
                        now_str, new_gov, new_lat, new_lon, new_src, new_crop, new_area, new_irrig,
                        client_ip, client_ip, geo.get("city", ""), geo.get("city", ""),
                        geo.get("isp", ""), geo.get("isp", ""), visitor_id,
                    ),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO visitor_profiles (
                        visitor_id, first_seen_at, last_seen_at, user_id,
                        pinned_governorate, gps_lat, gps_lon, location_source,
                        primary_crop, farm_size_feddan, irrigation_type,
                        last_ip, ip_city, isp, device_type, browser_os, visit_count
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                    """,
                    (
                        visitor_id, now_str, now_str, user_id,
                        gov_clean or "القاهرة", gps_lat, gps_lon, location_source,
                        primary_crop or "", float(farm_size_feddan or 1.0), irrigation_type or "غمر",
                        client_ip, geo.get("city", ""), geo.get("isp", ""), device_type, browser_os,
                    ),
                )
        conn.commit()
    return get_pinned_visitor_profile(visitor_id=visitor_id, user_id=user_id)


def get_pinned_visitor_profile(visitor_id: str = "", user_id: Optional[int] = None) -> Dict[str, Any]:
    """Retrieve the saved/pinned location & farm preferences for a visitor cookie or logged-in user."""
    init_db()
    out: Dict[str, Any] = {
        "visitor_id": visitor_id,
        "user_id": user_id,
        "user_name": "",
        "governorate": "القاهرة",
        "gps_lat": None,
        "gps_lon": None,
        "location_source": "default",
        "primary_crop": "",
        "farm_size_feddan": 1.0,
        "irrigation_type": "غمر",
    }
    try:
        with sqlite3.connect(str(DB_PATH), timeout=10.0) as conn:
            conn.row_factory = sqlite3.Row
            if visitor_id:
                v_row = conn.execute("SELECT * FROM visitor_profiles WHERE visitor_id = ?", (visitor_id,)).fetchone()
                if v_row:
                    out["user_id"] = user_id or v_row["user_id"]
                    out["user_name"] = v_row["user_name"] or ""
                    if v_row["pinned_governorate"]:
                        out["governorate"] = v_row["pinned_governorate"]
                    if v_row["gps_lat"] is not None and v_row["gps_lon"] is not None:
                        out["gps_lat"] = float(v_row["gps_lat"])
                        out["gps_lon"] = float(v_row["gps_lon"])
                    if v_row["location_source"]:
                        out["location_source"] = v_row["location_source"]
                    if v_row["primary_crop"]:
                        out["primary_crop"] = v_row["primary_crop"]
                    if v_row["farm_size_feddan"]:
                        out["farm_size_feddan"] = float(v_row["farm_size_feddan"])
                    if v_row["irrigation_type"]:
                        out["irrigation_type"] = v_row["irrigation_type"]

            effective_uid = out["user_id"]
            if effective_uid:
                u_row = conn.execute("SELECT * FROM users WHERE id = ?", (int(effective_uid),)).fetchone()
                if u_row:
                    out["user_name"] = u_row["full_name"] or out["user_name"]
                    if out["location_source"] in ("default", "ip") and u_row["governorate"]:
                        out["governorate"] = u_row["governorate"]
                        out["location_source"] = u_row["location_source"] or "user_profile"
                    if out["gps_lat"] is None and u_row["gps_lat"] is not None:
                        out["gps_lat"] = float(u_row["gps_lat"])
                        out["gps_lon"] = float(u_row["gps_lon"])
                        out["location_source"] = "gps"
                    if not out["primary_crop"] and u_row["primary_crop"]:
                        out["primary_crop"] = u_row["primary_crop"]
                    if u_row["farm_size_feddan"]:
                        out["farm_size_feddan"] = float(u_row["farm_size_feddan"])
                    if u_row["irrigation_type"]:
                        out["irrigation_type"] = u_row["irrigation_type"]
    except Exception:
        pass
    return out


def register_user(
    full_name: str,
    identifier_raw: str,
    password: str,
    governorate: str = "القاهرة",
    primary_crop: str = "",
    client_ip: str = "",
    device_type: str = "",
    confirm_password: Optional[str] = None,
    farm_size_feddan: float = 1.0,
    irrigation_type: str = "غمر",
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Register a new farmer/user account with strict data validation and return (user_dict, error_msg)."""
    init_db()
    cleaned_data, val_err = validate_new_user_data(
        full_name=full_name,
        identifier_raw=identifier_raw,
        password=password,
        confirm_password=confirm_password,
        governorate=governorate,
        primary_crop=primary_crop,
    )
    if val_err or not cleaned_data:
        return None, val_err or "البيانات المدخلة غير صحيحة."

    name = cleaned_data["full_name"]
    identifier = cleaned_data["identifier"]
    phone = cleaned_data["phone"]
    email = cleaned_data["email"]
    gov_clean = cleaned_data["governorate"]
    crop_clean = cleaned_data["primary_crop"]
    try:
        area_val = max(0.1, min(10000.0, float(farm_size_feddan or 1.0)))
    except Exception:
        area_val = 1.0
    irrig_clean = (irrigation_type or "غمر").strip()
    if irrig_clean not in ("غمر", "تنقيط", "رش", "drip", "surface", "sprinkler"):
        irrig_clean = "غمر"

    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    geo = resolve_ip_geo(client_ip)
    pw_hash = hash_password(password)

    with sqlite3.connect(str(DB_PATH)) as conn:
        conn.row_factory = sqlite3.Row
        existing = conn.execute(
            "SELECT id FROM users WHERE identifier = ? OR (phone != '' AND phone = ?) OR (email != '' AND email = ?)",
            (identifier, phone or "__none__", email or "__none__"),
        ).fetchone()
        if existing:
            return None, "هذا الحساب (رقم الموبايل أو البريد الإلكتروني) مسجل بالفعل. يمكنك تسجيل الدخول مباشرة."

        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO users (
                created_at, last_login_at, full_name, identifier, phone, email,
                governorate, primary_crop, password_hash, role, is_active,
                login_count, client_ip, device_type, geo_city,
                farm_size_feddan, irrigation_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'user', 1, 1, ?, ?, ?, ?, ?)
            """,
            (
                now_str,
                now_str,
                name,
                identifier,
                phone,
                email,
                gov_clean,
                crop_clean,
                pw_hash,
                client_ip or "",
                device_type or "",
                geo.get("city", ""),
                area_val,
                irrig_clean,
            ),
        )
        conn.commit()
        uid = int(cur.lastrowid)
        row = conn.execute(
            "SELECT id, created_at, last_login_at, full_name, identifier, phone, email, governorate, primary_crop, farm_size_feddan, irrigation_type, role, login_count FROM users WHERE id = ?",
            (uid,),
        ).fetchone()
        return (dict(row) if row else None), None


def authenticate_user(
    identifier_raw: str,
    password: str,
    client_ip: str = "",
    device_type: str = "",
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Authenticate user by phone, email, or admin alias ('abdo') and password."""
    init_db()
    raw_clean = (identifier_raw or "").strip().lower()
    identifier, phone, email = normalize_identifier(identifier_raw)
    if not identifier and not raw_clean:
        return None, "يرجى إدخال رقم الموبايل أو البريد الإلكتروني."

    with sqlite3.connect(str(DB_PATH)) as conn:
        conn.row_factory = sqlite3.Row
        if raw_clean in ("abdo", "admin", "developer"):
            row = conn.execute("SELECT * FROM users WHERE role = 'admin' LIMIT 1").fetchone()
        else:
            row = conn.execute(
                """
                SELECT * FROM users
                WHERE identifier = ?
                   OR (phone != '' AND phone = ?)
                   OR (email != '' AND email = ?)
                LIMIT 1
                """,
                (identifier, phone or identifier, email or raw_clean),
            ).fetchone()

        if not row:
            return None, "بيانات الدخول غير صحيحة أو الحساب غير مسجل."

        if not verify_password(password or "", row["password_hash"]):
            return None, "كلمة المرور غير صحيحة."

        if not int(row["is_active"] or 1):
            return None, "هذا الحساب موقوف حالياً."

        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        geo = resolve_ip_geo(client_ip)
        conn.execute(
            """
            UPDATE users
            SET last_login_at = ?,
                login_count = COALESCE(login_count, 0) + 1,
                client_ip = CASE WHEN ? != '' THEN ? ELSE client_ip END,
                device_type = CASE WHEN ? != '' THEN ? ELSE device_type END,
                geo_city = CASE WHEN ? != '' THEN ? ELSE geo_city END
            WHERE id = ?
            """,
            (
                now_str,
                client_ip, client_ip,
                device_type, device_type,
                geo.get("city", ""), geo.get("city", ""),
                row["id"],
            ),
        )
        conn.commit()
        updated = conn.execute(
            "SELECT id, created_at, last_login_at, full_name, identifier, phone, email, governorate, primary_crop, farm_size_feddan, irrigation_type, role, login_count, auth_provider, avatar_url FROM users WHERE id = ?",
            (row["id"],),
        ).fetchone()
        return (dict(updated) if updated else None), None


def social_or_quick_authenticate(
    provider: str,
    identifier_raw: str,
    full_name: str = "",
    governorate: str = "القاهرة",
    primary_crop: str = "",
    farm_size_feddan: float = 1.0,
    irrigation_type: str = "تنقيط",
    avatar_url: str = "",
    client_ip: str = "",
    device_type: str = "",
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Sign in or auto-register a user via Google, Microsoft, Apple, One-Tap Phone, or Passkey without password friction."""
    init_db()
    prov = (provider or "google").strip().lower()
    if prov not in ("google", "facebook", "yahoo", "microsoft", "apple", "quick_phone", "passkey"):
        prov = "google"

    identifier, phone, email = normalize_identifier(identifier_raw)
    if not identifier:
        return None, "يرجى إدخال البريد الإلكتروني أو رقم الموبايل الصحيح للمتابعة."

    if prov == "quick_phone" and not phone:
        return None, "يرجى إدخال رقم موبايل مصري صحيح مكون من 11 رقماً (يبدأ بـ 010 أو 011 أو 012 أو 015)."

    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    geo = resolve_ip_geo(client_ip)

    with sqlite3.connect(str(DB_PATH), timeout=15.0) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT * FROM users
            WHERE identifier = ?
               OR (phone != '' AND phone = ?)
               OR (email != '' AND email = ?)
            LIMIT 1
            """,
            (identifier, phone or "__none__", email or "__none__"),
        ).fetchone()

        if row:
            if not int(row["is_active"] or 1):
                return None, "هذا الحساب موقوف حالياً."
            new_name = (full_name or "").strip() or row["full_name"]
            new_gov = (governorate or "").strip() or row["governorate"] or "القاهرة"
            new_crop = (primary_crop or "").strip() or row["primary_crop"] or ""
            new_avatar = (avatar_url or "").strip() or row["avatar_url"] or ""
            conn.execute(
                """
                UPDATE users
                SET last_login_at = ?,
                    login_count = COALESCE(login_count, 0) + 1,
                    full_name = ?,
                    governorate = ?,
                    primary_crop = ?,
                    auth_provider = CASE WHEN auth_provider = 'password' OR auth_provider = '' THEN ? ELSE auth_provider END,
                    avatar_url = CASE WHEN ? != '' THEN ? ELSE avatar_url END,
                    client_ip = CASE WHEN ? != '' THEN ? ELSE client_ip END,
                    device_type = CASE WHEN ? != '' THEN ? ELSE device_type END,
                    geo_city = CASE WHEN ? != '' THEN ? ELSE geo_city END
                WHERE id = ?
                """,
                (
                    now_str,
                    new_name,
                    new_gov,
                    new_crop,
                    prov,
                    new_avatar, new_avatar,
                    client_ip, client_ip,
                    device_type, device_type,
                    geo.get("city", ""), geo.get("city", ""),
                    row["id"],
                ),
            )
            conn.commit()
            updated = conn.execute(
                "SELECT id, created_at, last_login_at, full_name, identifier, phone, email, governorate, primary_crop, farm_size_feddan, irrigation_type, role, login_count, auth_provider, avatar_url FROM users WHERE id = ?",
                (row["id"],),
            ).fetchone()
            return (dict(updated) if updated else None), None

        # Auto-create new account seamlessly
        clean_name = re.sub(r"\s+", " ", (full_name or "").strip())
        if len(clean_name) < 2:
            if email:
                clean_name = email.split("@")[0].replace(".", " ").replace("_", " ").strip().title()
            else:
                clean_name = f"مزارع ({phone[-4:]})" if phone else "مزارع ذكي"

        gov_clean = (governorate or "القاهرة").strip()
        if gov_clean not in VALID_EGYPT_GOVERNORATES:
            gov_clean = "القاهرة"
        crop_clean = (primary_crop or "").strip()
        try:
            area_val = max(0.1, min(10000.0, float(farm_size_feddan or 1.0)))
        except Exception:
            area_val = 1.0
        irrig_clean = (irrigation_type or "تنقيط").strip()
        if irrig_clean not in ("غمر", "تنقيط", "رش", "drip", "surface", "sprinkler"):
            irrig_clean = "تنقيط"

        auto_pw_hash = hash_password(secrets.token_urlsafe(24))
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO users (
                created_at, last_login_at, full_name, identifier, phone, email,
                governorate, primary_crop, password_hash, role, is_active,
                login_count, client_ip, device_type, geo_city,
                farm_size_feddan, irrigation_type, auth_provider, avatar_url
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'user', 1, 1, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                now_str,
                now_str,
                clean_name,
                identifier,
                phone,
                email,
                gov_clean,
                crop_clean,
                auto_pw_hash,
                client_ip or "",
                device_type or "",
                geo.get("city", ""),
                area_val,
                irrig_clean,
                prov,
                avatar_url or "",
            ),
        )
        conn.commit()
        uid = int(cur.lastrowid)
        created = conn.execute(
            "SELECT id, created_at, last_login_at, full_name, identifier, phone, email, governorate, primary_crop, farm_size_feddan, irrigation_type, role, login_count, auth_provider, avatar_url FROM users WHERE id = ?",
            (uid,),
        ).fetchone()
        return (dict(created) if created else None), None


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """Return user profile + personal activity counts by ID."""
    init_db()
    with sqlite3.connect(str(DB_PATH)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT id, created_at, last_login_at, full_name, identifier, phone, email, governorate, primary_crop, farm_size_feddan, irrigation_type, role, login_count, auth_provider, avatar_url FROM users WHERE id = ?",
            (int(user_id),),
        ).fetchone()
        if not row:
            return None
        user_d = dict(row)
        user_d["diagnoses_count"] = conn.execute(
            "SELECT COUNT(*) FROM uploaded_images WHERE user_id = ?", (int(user_id),)
        ).fetchone()[0]
        user_d["chats_count"] = conn.execute(
            "SELECT COUNT(*) FROM chat_logs WHERE user_id = ?", (int(user_id),)
        ).fetchone()[0]
        return user_d


def get_user_history(user_id: int, limit: int = 20) -> Dict[str, Any]:
    """Return a logged-in farmer's personal diagnosis & chat history."""
    init_db()
    with sqlite3.connect(str(DB_PATH)) as conn:
        conn.row_factory = sqlite3.Row
        imgs = conn.execute(
            """
            SELECT id, created_at, filename, model_used, predicted_class, predicted_class_ar,
                   confidence, rag_advice, weather_snapshot
            FROM uploaded_images
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (int(user_id), limit),
        ).fetchall()
        chats = conn.execute(
            """
            SELECT id, created_at, location, crop, user_query, bot_answer, topic_category
            FROM chat_logs
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (int(user_id), limit),
        ).fetchall()
        return {
            "diagnoses": [dict(r) for r in imgs],
            "chats": [dict(r) for r in chats],
        }
