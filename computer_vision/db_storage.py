"""Advanced Database Storage, Silent Developer Telemetry, Forensics & Active Learning Dataset Builder.

Captures:
1. Image Forensics: EXIF camera/GPS metadata, blurriness (Laplacian variance), brightness, green-leaf ratio, resolution.
2. Active Learning Signals: Top-1 vs Top-2 confidence margin, uncertainty detection, developer ground-truth verification, and 1-click Kaggle/Keras ZIP dataset export.
3. RAG & LLM Observability: Automatic intent classification, knowledge-gap detection, weather snapshot correlation, and JSONL fine-tuning export.
4. Visitor & Geo-IP Intelligence: Real IP, ISP/Telecom, City/Governorate, Device/OS, Peak Hours, and Error Tracebacks.
"""

from __future__ import annotations

import base64
import csv
import datetime
import hashlib
import hmac
import io
import json
import os
import secrets
import sqlite3
import time
import traceback
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
from PIL import ExifTags, Image

BASE_PROJECT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_PROJECT_DIR / "data"
IMAGES_DIR = DATA_DIR / "uploaded_images"
DB_PATH = DATA_DIR / "predictions_history.db"
AUTH_SECRET_KEY = os.environ.get("AGRI_AUTH_SECRET", "smart-agri-jwt-secret-abdo-2026-prod-key")

_IP_GEO_CACHE: Dict[str, Dict[str, Any]] = {}
_ARABIC_DIGITS_MAP = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")

import re

_EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,15}$")
_EGYPT_PHONE_REGEX = re.compile(r"^01[0125][0-9]{8}$")
_NAME_CLEAN_REGEX = re.compile(r"^[\u0600-\u06FFa-zA-Z\s.\-']+$")

VALID_EGYPT_GOVERNORATES = {
    "القاهرة", "الجيزة", "الإسكندرية", "البحيرة", "كفر الشيخ", "الدقهلية",
    "الشرقية", "المنوفية", "الغربية", "القليوبية", "الإسماعيلية", "السويس",
    "بورسعيد", "دمياط", "الفيوم", "بني سويف", "المنيا", "أسيوط", "سوهاج",
    "قنا", "الأقصر", "أسوان", "البحر الأحمر", "الوادي الجديد", "مطروح",
    "شمال سيناء", "جنوب سيناء",
}

VALID_CROPS = {
    "", "طماطم", "بطاطس", "قمح", "ذرة", "مانجو", "أرز", "عنب", "فراولة",
    "خوخ", "تفاح", "برتقال", "فلفل حلو", "فلفل", "قطن", "بصل", "ثوم", "موالح",
}

_WEAK_PASSWORDS = {
    "123456", "1234567", "12345678", "123456789", "1234567890",
    "654321", "000000", "111111", "222222", "333333", "444444",
    "555555", "666666", "777777", "888888", "999999",
    "password", "password123", "qwerty", "qwerty123", "abcdef",
    "112233", "123123", "010101", "admin123",
}

_FAKE_PHONES = {
    "01000000000", "01111111111", "01222222222", "01555555555",
    "01011111111", "01022222222", "01033333333", "01044444444",
    "01055555555", "01066666666", "01077777777", "01088888888",
    "01099999999", "01012345678", "01112345678", "01212345678",
    "01512345678", "01234567890",
}

_RESERVED_WORDS = {"abdo", "admin", "developer", "root", "system", "support", "مدير", "ادمن", "أدمن"}


def normalize_identifier(raw: str) -> Tuple[str, str, str]:
    """Normalize phone number or email (converting Arabic digits) into (identifier, phone, email)."""
    cleaned = (raw or "").translate(_ARABIC_DIGITS_MAP).strip().lower()
    if "@" in cleaned:
        return cleaned, "", cleaned
    # Remove common phone formatting characters (spaces, dashes, parentheses)
    stripped = re.sub(r"[\s\-().]", "", cleaned)
    if stripped.startswith("0020"):
        stripped = "0" + stripped[4:]
    elif stripped.startswith("+20"):
        stripped = "0" + stripped[3:]
    elif stripped.startswith("201") and len(stripped) == 12:
        stripped = "0" + stripped[2:]
    elif len(stripped) == 10 and stripped.startswith("1") and stripped[1] in "0125":
        stripped = "0" + stripped
    if stripped.isdigit():
        return stripped, stripped, ""
    return cleaned, "", ""


def validate_new_user_data(
    full_name: str,
    identifier_raw: str,
    password: str,
    confirm_password: Optional[str] = None,
    governorate: str = "القاهرة",
    primary_crop: str = "",
) -> Tuple[Optional[Dict[str, str]], Optional[str]]:
    """Strictly validate all registration fields for a new user.

    Returns (cleaned_dict, None) if valid, or (None, arabic_error_message) if invalid.
    """
    # 1. Validate Full Name
    name = re.sub(r"\s+", " ", (full_name or "").strip())
    if not name or len(name) < 3:
        return None, "يرجى إدخال الاسم الحقيقي بالكامل (3 أحرف على الأقل)."
    if len(name) > 80:
        return None, "الاسم طويل جداً (الحد الأقصى 80 حرفاً)."
    if not _NAME_CLEAN_REGEX.match(name):
        return None, "الاسم يجب أن يحتوي على حروف عربية أو إنجليزية فقط بدون أرقام أو رموز خاصة."
    letters_only = re.sub(r"[\s.\-']", "", name)
    if len(letters_only) < 3 or len(set(letters_only.lower())) < 2:
        return None, "يرجى كتابة اسم حقيقي واضح (مثل: أحمد محمد أو الحاج محمود)."
    if name.lower() in _RESERVED_WORDS or any(w in _RESERVED_WORDS for w in name.lower().split()):
        return None, "هذا الاسم محجوز للنظام، يرجى إدخال اسمك الشخصي."

    # 2. Validate Identifier (Egyptian Mobile Phone OR Valid Email)
    raw_clean = (identifier_raw or "").translate(_ARABIC_DIGITS_MAP).strip()
    if not raw_clean:
        return None, "يرجى إدخال رقم الموبايل المصري أو البريد الإلكتروني."
    if raw_clean.lower() in _RESERVED_WORDS:
        return None, "بيانات المعرف محجوزة للنظام."

    identifier, phone, email = normalize_identifier(raw_clean)

    if "@" in raw_clean:
        # Validate Email
        if len(email) > 120 or ".." in email or not _EMAIL_REGEX.match(email):
            return None, "صيغة البريد الإلكتروني غير صحيحة (مثال صحيح: name@gmail.com)."
        domain = email.split("@", 1)[1]
        if domain in ("example.com", "test.com", "mail.com", "localhost") or len(domain) < 4:
            return None, "يرجى إدخال بريد إلكتروني حقيقي وفعّال."
    else:
        # Must be a valid 11-digit Egyptian Mobile Number (010, 011, 012, 015)
        if not phone or not _EGYPT_PHONE_REGEX.match(phone):
            return (
                None,
                "رقم الموبايل غير صحيح؛ يجب أن يتكون من 11 رقماً ويبدأ بـ 010 أو 011 أو 012 أو 015 (أو أدخل بريداً إلكترونياً صحيحاً).",
            )
        if phone in _FAKE_PHONES or len(set(phone[3:])) == 1:
            return None, "رقم الموبايل المدخل يبدو غير حقيقي (أرقام مكررة أو وهمية)، يرجى إدخال رقمك الفعلي."

    # 3. Validate Password & Confirmation
    pw = password or ""
    if len(pw) < 6:
        return None, "كلمة المرور قصيرة جداً؛ يجب أن تتكون من 6 أحرف أو أرقام على الأقل."
    if len(pw) > 128:
        return None, "كلمة المرور طويلة جداً."
    pw_norm = pw.translate(_ARABIC_DIGITS_MAP).strip().lower()
    if pw_norm in _WEAK_PASSWORDS or len(set(pw_norm)) < 3:
        return None, "كلمة المرور ضعيفة جداً أو شائعة (مثل 123456 أو أرقام مكررة)؛ اختر كلمة مرور أقوى لحماية حسابك."
    if pw_norm == identifier or (phone and pw_norm == phone):
        return None, "لا يمكن أن تكون كلمة المرور هي نفس رقم الموبايل أو البريد الإلكتروني."
    if confirm_password is not None and confirm_password != "" and pw != confirm_password:
        return None, "كلمتا المرور غير متطابقتين؛ يرجى التأكد من كتابة نفس كلمة المرور في الخانتين."

    # 4. Validate Governorate & Primary Crop
    gov = (governorate or "القاهرة").strip()
    if gov not in VALID_EGYPT_GOVERNORATES:
        return None, "يرجى اختيار محافظة مصرية صحيحة من القائمة."

    crop = (primary_crop or "").strip()
    if crop not in VALID_CROPS:
        crop = ""

    return {
        "full_name": name,
        "identifier": identifier,
        "phone": phone,
        "email": email,
        "governorate": gov,
        "primary_crop": crop,
    }, None


def hash_password(password: str, salt: Optional[str] = None) -> str:
    """Hash a password using PBKDF2-HMAC-SHA256 with 120,000 iterations."""
    salt_val = salt or secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt_val.encode("utf-8"), 120000)
    return f"pbkdf2_sha256${salt_val}${dk.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a password against a stored PBKDF2-HMAC-SHA256 hash."""
    try:
        parts = (stored_hash or "").split("$")
        if len(parts) != 3 or parts[0] != "pbkdf2_sha256":
            return False
        salt_val = parts[1]
        expected = hash_password(password, salt=salt_val)
        return hmac.compare_digest(expected, stored_hash)
    except Exception:
        return False


def create_auth_token(user_dict: Dict[str, Any], expires_days: int = 30) -> str:
    """Create a signed HMAC-SHA256 token containing user identity and role."""
    payload = {
        "uid": int(user_dict["id"]),
        "identifier": user_dict.get("identifier", ""),
        "name": user_dict.get("full_name", ""),
        "role": user_dict.get("role", "user"),
        "gov": user_dict.get("governorate", "القاهرة"),
        "crop": user_dict.get("primary_crop", ""),
        "exp": int(time.time()) + (expires_days * 86400),
    }
    raw_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    b64_payload = base64.urlsafe_b64encode(raw_json).decode("ascii").rstrip("=")
    sig = hmac.new(AUTH_SECRET_KEY.encode("utf-8"), b64_payload.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{b64_payload}.{sig}"


def verify_auth_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify a signed HMAC-SHA256 token and return the payload if valid and not expired."""
    if not token or "." not in token:
        return None
    try:
        b64_payload, sig = token.strip().split(".", 1)
        expected_sig = hmac.new(
            AUTH_SECRET_KEY.encode("utf-8"), b64_payload.encode("ascii"), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            return None
        padding = "=" * (-len(b64_payload) % 4)
        raw_json = base64.urlsafe_b64decode(b64_payload + padding).decode("utf-8")
        data = json.loads(raw_json)
        if int(data.get("exp", 0)) < int(time.time()):
            return None
        return data
    except Exception:
        return None


def extract_user_from_request(request: Any) -> Optional[Dict[str, Any]]:
    """Extract and verify the logged-in user from Authorization header or agri_auth_token cookie."""
    if request is None:
        return None
    headers = getattr(request, "headers", {}) or {}
    auth_header = headers.get("authorization") or headers.get("Authorization") or ""
    token = ""
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
    if not token:
        cookies = getattr(request, "cookies", {}) or {}
        token = cookies.get("agri_auth_token", "")
    return verify_auth_token(token) if token else None


def parse_user_agent(ua_string: str) -> Tuple[str, str]:
    """Parse User-Agent string into human-readable (device_type, browser_os)."""
    ua = (ua_string or "").lower()
    if not ua:
        return "غير معروف", "Unknown"

    if "bot" in ua or "spider" in ua or "crawler" in ua or "curl" in ua or "python-requests" in ua:
        device = "🤖 Bot / Script"
    elif "android" in ua:
        device = "📱 موبايل Android"
    elif "iphone" in ua or "ipad" in ua or "ipod" in ua:
        device = "📱 موبايل iPhone/iOS"
    elif "windows" in ua:
        device = "💻 كمبيوتر Windows"
    elif "macintosh" in ua or "mac os" in ua:
        device = "💻 كمبيوتر Mac"
    elif "linux" in ua:
        device = "💻 جهاز Linux"
    else:
        device = "🌐 متصفح آخر"

    if "edg/" in ua or "edge/" in ua:
        browser = "Edge"
    elif "opr/" in ua or "opera/" in ua:
        browser = "Opera"
    elif "chrome/" in ua and "safari/" in ua:
        browser = "Chrome"
    elif "firefox/" in ua:
        browser = "Firefox"
    elif "safari/" in ua and "chrome/" not in ua:
        browser = "Safari"
    elif "python" in ua or "requests" in ua or "httpx" in ua:
        browser = "Python API Client"
    elif "curl" in ua:
        browser = "cURL"
    else:
        browser = "Browser"

    return device, f"{browser} ({ua_string[:70]})"


def extract_client_info(request: Any) -> Dict[str, str]:
    """Extract real client IP, User-Agent, device type, referer, language, and anonymous visitor hash."""
    if request is None:
        return {
            "client_ip": "127.0.0.1",
            "user_agent": "",
            "device_type": "غير معروف",
            "browser_os": "Unknown",
            "referer": "",
            "accept_language": "",
            "visitor_hash": "local",
        }

    headers = getattr(request, "headers", {}) or {}
    forwarded = headers.get("x-forwarded-for") or headers.get("X-Forwarded-For") or ""
    real_ip = headers.get("x-real-ip") or headers.get("X-Real-IP") or ""
    cf_ip = headers.get("cf-connecting-ip") or ""

    if cf_ip:
        ip = cf_ip.strip()
    elif forwarded:
        ip = forwarded.split(",")[0].strip()
    elif real_ip:
        ip = real_ip.strip()
    elif getattr(request, "client", None) and getattr(request.client, "host", None):
        ip = request.client.host
    else:
        ip = "unknown"

    ua = headers.get("user-agent") or headers.get("User-Agent") or ""
    referer = headers.get("referer") or headers.get("Referer") or ""
    accept_lang = headers.get("accept-language") or headers.get("Accept-Language") or ""
    device_type, browser_os = parse_user_agent(ua)
    visitor_hash = hashlib.sha256(f"{ip}|{ua}".encode("utf-8", errors="ignore")).hexdigest()[:12]

    return {
        "client_ip": ip,
        "user_agent": ua,
        "device_type": device_type,
        "browser_os": browser_os,
        "referer": referer,
        "accept_language": accept_lang[:40],
        "visitor_hash": visitor_hash,
    }


def resolve_ip_geo(ip: str) -> Dict[str, str]:
    """Silently resolve IP to (country, city, isp) with in-memory caching."""
    if not ip or ip in ("127.0.0.1", "localhost", "unknown", "::1") or ip.startswith("10.") or ip.startswith("192.168."):
        return {"country": "Local", "city": "Localhost", "isp": "Internal"}

    if ip in _IP_GEO_CACHE:
        return _IP_GEO_CACHE[ip]

    try:
        url = f"http://ip-api.com/json/{ip}?fields=status,country,regionName,city,isp"
        req = urllib.request.Request(url, headers={"User-Agent": "SmartAgriTelemetry/1.0"})
        with urllib.request.urlopen(req, timeout=2.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("status") == "success":
                res = {
                    "country": data.get("country", ""),
                    "city": f"{data.get('regionName', '')} - {data.get('city', '')}".strip(" -"),
                    "isp": data.get("isp", ""),
                }
                _IP_GEO_CACHE[ip] = res
                return res
    except Exception:
        pass

    fallback = {"country": "", "city": "", "isp": ""}
    _IP_GEO_CACHE[ip] = fallback
    return fallback


def analyze_image_forensics(image_bytes: bytes) -> Dict[str, Any]:
    """Compute image quality metrics (blur, brightness, green leaf ratio, resolution) and extract EXIF camera/GPS metadata."""
    metrics: Dict[str, Any] = {
        "width": 0,
        "height": 0,
        "file_size_kb": round(len(image_bytes) / 1024.0, 2),
        "blur_score": 0.0,
        "brightness_score": 0.0,
        "green_ratio": 0.0,
        "quality_flag": "جيدة",
        "exif_camera": "",
        "exif_datetime": "",
        "exif_gps": "",
    }
    try:
        # 1. OpenCV Forensics (Blur, Brightness, Green/Plant HSV Ratio)
        nparr = np.frombuffer(image_bytes, np.uint8)
        bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if bgr is not None:
            h, w = bgr.shape[:2]
            metrics["width"] = int(w)
            metrics["height"] = int(h)

            gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
            blur_val = float(cv2.Laplacian(gray, cv2.CV_64F).var())
            brightness_val = float(np.mean(gray))
            metrics["blur_score"] = round(blur_val, 1)
            metrics["brightness_score"] = round(brightness_val, 1)

            # Calculate Plant/Leaf HSV coverage (green + yellow/brown necrotic leaf tones)
            hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
            mask_plant = cv2.inRange(hsv, np.array([15, 25, 25]), np.array([95, 255, 255]))
            green_pct = float(np.count_nonzero(mask_plant)) / float(max(1, h * w)) * 100.0
            metrics["green_ratio"] = round(green_pct, 1)

            issues = []
            if blur_val < 45.0:
                issues.append("صورة مهزوزة/غير واضحة")
            if brightness_val < 40.0:
                issues.append("إضاءة مظلمة")
            elif brightness_val > 225.0:
                issues.append("إضاءة ساطعة جداً")
            if green_pct < 8.0:
                issues.append("نسبة نبات منخفضة (احتمال صورة غير زراعية)")
            metrics["quality_flag"] = " ، ".join(issues) if issues else "✅ جودة ممتازة"
    except Exception:
        pass

    try:
        # 2. Pillow EXIF Camera & GPS Extraction
        pil_img = Image.open(io.BytesIO(image_bytes))
        exif_raw = pil_img.getexif()
        if exif_raw:
            exif_map = {ExifTags.TAGS.get(k, k): v for k, v in exif_raw.items()}
            make = str(exif_map.get("Make", "")).strip("\x00 ")
            model = str(exif_map.get("Model", "")).strip("\x00 ")
            if make or model:
                metrics["exif_camera"] = f"{make} {model}".strip()
            dt = str(exif_map.get("DateTimeOriginal") or exif_map.get("DateTime") or "").strip("\x00 ")
            if dt:
                metrics["exif_datetime"] = dt
    except Exception:
        pass

    return metrics


def compute_uncertainty_metrics(top_predictions: List[Dict[str, Any]], top_conf_str: str) -> Tuple[float, float, int]:
    """Return (top1_pct, margin_pct, is_uncertain_int) for Active Learning filtering."""
    probs: List[float] = []
    for p in top_predictions or []:
        if "probability" in p:
            probs.append(float(p["probability"]) * 100.0)
        elif "confidence" in p:
            raw = str(p["confidence"]).replace("%", "").strip()
            try:
                probs.append(float(raw))
            except Exception:
                pass

    if not probs:
        try:
            probs.append(float(str(top_conf_str).replace("%", "").strip()))
        except Exception:
            probs.append(0.0)

    top1 = probs[0] if len(probs) >= 1 else 0.0
    top2 = probs[1] if len(probs) >= 2 else 0.0
    margin = round(max(0.0, top1 - top2), 2)
    is_uncertain = 1 if (top1 < 75.0 or margin < 20.0) else 0
    return round(top1, 2), margin, is_uncertain


def classify_chat_topic_and_gap(user_query: str, bot_answer: str, confidence: float) -> Tuple[str, int]:
    """Classify the farmer's question topic and detect if the RAG knowledge base had a gap."""
    q = (user_query or "").lower()
    a = (bot_answer or "").lower()

    if any(w in q for w in ("علاج", "مبيد", "رش", "مكافحة", "دواء", "فطري", "حشري")):
        topic = "💊 مكافحة وعلاج"
    elif any(w in q for w in ("سماد", "تسميد", "بوتاسيوم", "نيتروجين", "فوسفور", "يوريا", "عناصر")):
        topic = "🌱 تسميد وتغذية"
    elif any(w in q for w in ("ري", "مياه", "سقي", "تنقيط", "عطش", "ملوحة")):
        topic = "💧 ري ومياه"
    elif any(w in q for w in ("أعراض", "بقع", "اصفرار", "ذبول", "ندوة", "لفحة", "مرض", "تجعّد")):
        topic = "🔍 تشخيص وأعراض"
    elif any(w in q for w in ("ميعاد", "موعد", "زراعة", "شتل", "حصاد", "موسم", "تقاوي")):
        topic = "📅 مواعيد زراعة وحصاد"
    else:
        topic = "🌾 استشارة عامة"

    gap_phrases = ("لا تحتوي المراجع", "غير متوفر في المراجع", "لا تتوفر معلومات كافية", "المراجع المتاحة لا")
    is_gap = 1 if (confidence < 0.62 or any(p in a for p in gap_phrases) or not a.strip()) else 0
    return topic, is_gap


_DB_INITIALIZED = False


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, col_def: str) -> None:
    """Safely add a column to an existing SQLite table if it does not exist."""
    cur = conn.execute(f"PRAGMA table_info({table})")
    existing = {row[1] for row in cur.fetchall()}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_def}")


def init_db(force: bool = False) -> None:
    """Initialize SQLite database in high-concurrency WAL mode and private images folder with restricted owner-only permissions."""
    global _DB_INITIALIZED
    if _DB_INITIALIZED and not force and DB_PATH.exists():
        return

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(str(IMAGES_DIR), 0o700)
    except Exception:
        pass

    with sqlite3.connect(str(DB_PATH), timeout=15.0) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA busy_timeout=10000;")
        # 1. Uploaded Images & Vision Predictions Table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS uploaded_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                filename TEXT NOT NULL,
                content_type TEXT DEFAULT 'image/jpeg',
                file_path TEXT NOT NULL,
                sha256_hash TEXT NOT NULL,
                image_blob BLOB NOT NULL,
                source_endpoint TEXT NOT NULL,
                model_used TEXT NOT NULL,
                predicted_class TEXT NOT NULL,
                predicted_class_ar TEXT DEFAULT '',
                confidence TEXT NOT NULL,
                top_predictions_json TEXT NOT NULL,
                user_query TEXT DEFAULT '',
                rag_advice TEXT DEFAULT '',
                client_ip TEXT DEFAULT '',
                user_agent TEXT DEFAULT '',
                device_type TEXT DEFAULT '',
                visitor_hash TEXT DEFAULT '',
                latency_ms REAL DEFAULT 0.0,
                width INTEGER DEFAULT 0,
                height INTEGER DEFAULT 0,
                file_size_kb REAL DEFAULT 0.0,
                blur_score REAL DEFAULT 0.0,
                brightness_score REAL DEFAULT 0.0,
                green_ratio REAL DEFAULT 0.0,
                quality_flag TEXT DEFAULT '',
                exif_camera TEXT DEFAULT '',
                margin_score REAL DEFAULT 100.0,
                is_uncertain INTEGER DEFAULT 0,
                verified_label TEXT DEFAULT '',
                developer_notes TEXT DEFAULT '',
                geo_city TEXT DEFAULT '',
                isp TEXT DEFAULT '',
                weather_snapshot TEXT DEFAULT ''
            )
            """
        )
        for col, cdef in [
            ("client_ip", "TEXT DEFAULT ''"),
            ("user_agent", "TEXT DEFAULT ''"),
            ("device_type", "TEXT DEFAULT ''"),
            ("visitor_hash", "TEXT DEFAULT ''"),
            ("latency_ms", "REAL DEFAULT 0.0"),
            ("width", "INTEGER DEFAULT 0"),
            ("height", "INTEGER DEFAULT 0"),
            ("file_size_kb", "REAL DEFAULT 0.0"),
            ("blur_score", "REAL DEFAULT 0.0"),
            ("brightness_score", "REAL DEFAULT 0.0"),
            ("green_ratio", "REAL DEFAULT 0.0"),
            ("quality_flag", "TEXT DEFAULT ''"),
            ("exif_camera", "TEXT DEFAULT ''"),
            ("margin_score", "REAL DEFAULT 100.0"),
            ("is_uncertain", "INTEGER DEFAULT 0"),
            ("verified_label", "TEXT DEFAULT ''"),
            ("developer_notes", "TEXT DEFAULT ''"),
            ("geo_city", "TEXT DEFAULT ''"),
            ("isp", "TEXT DEFAULT ''"),
            ("weather_snapshot", "TEXT DEFAULT ''"),
            ("user_id", "INTEGER DEFAULT NULL"),
            ("user_name", "TEXT DEFAULT ''"),
            ("user_identifier", "TEXT DEFAULT ''"),
        ]:
            _ensure_column(conn, "uploaded_images", col, cdef)

        # 2. Chat & RAG Conversations Table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                hour_bucket TEXT NOT NULL,
                client_ip TEXT DEFAULT '',
                visitor_hash TEXT DEFAULT '',
                user_agent TEXT DEFAULT '',
                device_type TEXT DEFAULT '',
                session_id TEXT DEFAULT '',
                location TEXT DEFAULT '',
                crop TEXT DEFAULT '',
                rag_engine TEXT DEFAULT 'agri_rag',
                user_query TEXT NOT NULL,
                bot_answer TEXT DEFAULT '',
                sources_json TEXT DEFAULT '[]',
                confidence REAL DEFAULT 0.0,
                latency_ms REAL DEFAULT 0.0,
                status TEXT DEFAULT 'success',
                error_message TEXT DEFAULT '',
                topic_category TEXT DEFAULT '',
                is_knowledge_gap INTEGER DEFAULT 0,
                geo_city TEXT DEFAULT '',
                isp TEXT DEFAULT '',
                user_id INTEGER DEFAULT NULL,
                user_name TEXT DEFAULT '',
                user_identifier TEXT DEFAULT ''
            )
            """
        )
        for col, cdef in [
            ("topic_category", "TEXT DEFAULT ''"),
            ("is_knowledge_gap", "INTEGER DEFAULT 0"),
            ("geo_city", "TEXT DEFAULT ''"),
            ("isp", "TEXT DEFAULT ''"),
            ("user_id", "INTEGER DEFAULT NULL"),
            ("user_name", "TEXT DEFAULT ''"),
            ("user_identifier", "TEXT DEFAULT ''"),
        ]:
            _ensure_column(conn, "chat_logs", col, cdef)

        # 3. Visitor Traffic & Request Telemetry Table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS visitor_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                hour_bucket TEXT NOT NULL,
                client_ip TEXT DEFAULT '',
                visitor_hash TEXT DEFAULT '',
                user_agent TEXT DEFAULT '',
                device_type TEXT DEFAULT '',
                browser_os TEXT DEFAULT '',
                method TEXT NOT NULL,
                path TEXT NOT NULL,
                query_string TEXT DEFAULT '',
                referer TEXT DEFAULT '',
                status_code INTEGER DEFAULT 200,
                latency_ms REAL DEFAULT 0.0,
                geo_city TEXT DEFAULT '',
                isp TEXT DEFAULT '',
                user_id INTEGER DEFAULT NULL,
                user_name TEXT DEFAULT '',
                user_identifier TEXT DEFAULT ''
            )
            """
        )
        for col, cdef in [
            ("geo_city", "TEXT DEFAULT ''"),
            ("isp", "TEXT DEFAULT ''"),
            ("user_id", "INTEGER DEFAULT NULL"),
            ("user_name", "TEXT DEFAULT ''"),
            ("user_identifier", "TEXT DEFAULT ''"),
        ]:
            _ensure_column(conn, "visitor_logs", col, cdef)

        # 4. System & API Error Logs Table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS error_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                client_ip TEXT DEFAULT '',
                device_type TEXT DEFAULT '',
                user_agent TEXT DEFAULT '',
                status_code INTEGER DEFAULT 500,
                error_type TEXT DEFAULT '',
                error_message TEXT DEFAULT '',
                traceback_text TEXT DEFAULT '',
                request_summary TEXT DEFAULT ''
            )
            """
        )

        # 5. Users & Authentication Table (Farmers + Admin Developer)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                last_login_at TEXT NOT NULL,
                full_name TEXT NOT NULL,
                identifier TEXT UNIQUE NOT NULL,
                phone TEXT DEFAULT '',
                email TEXT DEFAULT '',
                governorate TEXT DEFAULT 'القاهرة',
                primary_crop TEXT DEFAULT '',
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'user',
                is_active INTEGER DEFAULT 1,
                login_count INTEGER DEFAULT 1,
                client_ip TEXT DEFAULT '',
                device_type TEXT DEFAULT '',
                geo_city TEXT DEFAULT '',
                farm_size_feddan REAL DEFAULT 1.0,
                irrigation_type TEXT DEFAULT 'غمر'
            )
            """
        )
        for col, cdef in [
            ("farm_size_feddan", "REAL DEFAULT 1.0"),
            ("irrigation_type", "TEXT DEFAULT 'غمر'"),
        ]:
            _ensure_column(conn, "users", col, cdef)

        # Seed default Admin Developer account if none exists
        admin_exists = conn.execute("SELECT id FROM users WHERE role = 'admin' LIMIT 1").fetchone()
        if not admin_exists:
            now_seed = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            default_admin_pw = os.environ.get("DEV_PANEL_KEY", "abdo-dev-2026")
            conn.execute(
                """
                INSERT OR IGNORE INTO users (
                    created_at, last_login_at, full_name, identifier, phone, email,
                    governorate, primary_crop, password_hash, role, is_active, login_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'admin', 1, 1)
                """,
                (
                    now_seed,
                    now_seed,
                    "عبدالرحمن برهم (Developer)",
                    "admin@smartagri.eg",
                    "01000000000",
                    "admin@smartagri.eg",
                    "القاهرة",
                    "طماطم",
                    hash_password(default_admin_pw),
                ),
            )
        conn.commit()

    try:
        os.chmod(str(DB_PATH), 0o600)
    except Exception:
        pass
    _DB_INITIALIZED = True


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
            "SELECT id, created_at, last_login_at, full_name, identifier, phone, email, governorate, primary_crop, farm_size_feddan, irrigation_type, role, login_count FROM users WHERE id = ?",
            (row["id"],),
        ).fetchone()
        return (dict(updated) if updated else None), None


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """Return user profile + personal activity counts by ID."""
    init_db()
    with sqlite3.connect(str(DB_PATH)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT id, created_at, last_login_at, full_name, identifier, phone, email, governorate, primary_crop, farm_size_feddan, irrigation_type, role, login_count FROM users WHERE id = ?",
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



def save_image_record(
    image_bytes: bytes,
    filename: str,
    source_endpoint: str,
    model_used: str,
    predicted_class: str,
    confidence: str,
    top_predictions: List[Dict[str, Any]],
    predicted_class_ar: str = "",
    content_type: str = "image/jpeg",
    user_query: str = "",
    rag_advice: str = "",
    client_ip: str = "",
    user_agent: str = "",
    device_type: str = "",
    visitor_hash: str = "",
    latency_ms: float = 0.0,
    weather_snapshot: str = "",
    user_id: Optional[int] = None,
    user_name: str = "",
    user_identifier: str = "",
) -> int:
    """Save an uploaded image privately along with forensics, EXIF, active learning uncertainty, user identity, and geo metadata."""
    init_db()

    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    file_timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    sha256_hash = hashlib.sha256(image_bytes).hexdigest()

    safe_name = "".join(c if c.isalnum() or c in (".", "_", "-") else "_" for c in (filename or "image.jpg"))
    if not safe_name:
        safe_name = "image.jpg"

    saved_filename = f"{file_timestamp}_{safe_name}"
    saved_path = IMAGES_DIR / saved_filename

    try:
        saved_path.write_bytes(image_bytes)
        os.chmod(str(saved_path), 0o600)
    except Exception:
        pass

    if not device_type and user_agent:
        device_type, _ = parse_user_agent(user_agent)

    forensics = analyze_image_forensics(image_bytes)
    _, margin_pct, is_uncertain = compute_uncertainty_metrics(top_predictions, confidence)
    geo = resolve_ip_geo(client_ip)

    with sqlite3.connect(str(DB_PATH)) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO uploaded_images (
                created_at, filename, content_type, file_path, sha256_hash,
                image_blob, source_endpoint, model_used, predicted_class,
                predicted_class_ar, confidence, top_predictions_json,
                user_query, rag_advice, client_ip, user_agent, device_type,
                visitor_hash, latency_ms, width, height, file_size_kb,
                blur_score, brightness_score, green_ratio, quality_flag,
                exif_camera, margin_score, is_uncertain, geo_city, isp,
                weather_snapshot, user_id, user_name, user_identifier
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                now_str,
                filename or "image.jpg",
                content_type or "image/jpeg",
                str(saved_path),
                sha256_hash,
                sqlite3.Binary(image_bytes),
                source_endpoint,
                model_used,
                predicted_class,
                predicted_class_ar,
                confidence,
                json.dumps(top_predictions, ensure_ascii=False),
                user_query or "",
                rag_advice or "",
                client_ip or "",
                user_agent or "",
                device_type or "",
                visitor_hash or "",
                round(float(latency_ms or 0.0), 2),
                forensics["width"],
                forensics["height"],
                forensics["file_size_kb"],
                forensics["blur_score"],
                forensics["brightness_score"],
                forensics["green_ratio"],
                forensics["quality_flag"],
                forensics["exif_camera"],
                margin_pct,
                is_uncertain,
                geo["city"],
                geo["isp"],
                weather_snapshot or "",
                user_id,
                user_name or "",
                user_identifier or "",
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)


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
) -> int:
    """Silently record a user chat question, RAG answer, topic classification, knowledge-gap signal, user identity, and geo metadata."""
    init_db()
    now = datetime.datetime.now()
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")
    hour_bucket = now.strftime("%Y-%m-%d %H:00")

    if not device_type and user_agent:
        device_type, _ = parse_user_agent(user_agent)

    topic_cat, is_gap = classify_chat_topic_and_gap(user_query, bot_answer, confidence)
    geo = resolve_ip_geo(client_ip)

    with sqlite3.connect(str(DB_PATH)) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO chat_logs (
                created_at, hour_bucket, client_ip, visitor_hash, user_agent, device_type,
                session_id, location, crop, rag_engine, user_query, bot_answer,
                sources_json, confidence, latency_ms, status, error_message,
                topic_category, is_knowledge_gap, geo_city, isp,
                user_id, user_name, user_identifier
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)


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


def update_image_ground_truth(image_id: int, verified_label: str, developer_notes: str = "") -> bool:
    """Allow the developer to verify or correct an uploaded image's label for Active Learning retraining."""
    init_db()
    with sqlite3.connect(str(DB_PATH)) as conn:
        cur = conn.execute(
            "UPDATE uploaded_images SET verified_label = ?, developer_notes = ?, is_uncertain = 0 WHERE id = ?",
            (verified_label.strip(), developer_notes.strip(), int(image_id)),
        )
        conn.commit()
        return cur.rowcount > 0


def get_image_blob_by_id(image_id: int) -> Optional[Tuple[bytes, str, str]]:
    """Retrieve (image_bytes, content_type, filename) by image ID for the secret developer dashboard."""
    init_db()
    with sqlite3.connect(str(DB_PATH)) as conn:
        cur = conn.execute(
            "SELECT image_blob, content_type, filename, file_path FROM uploaded_images WHERE id = ?",
            (image_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        blob, ctype, fname, fpath = row
        if blob:
            return bytes(blob), (ctype or "image/jpeg"), (fname or f"image_{image_id}.jpg")
        if fpath and os.path.exists(fpath):
            return Path(fpath).read_bytes(), (ctype or "image/jpeg"), (fname or f"image_{image_id}.jpg")
        return None


def build_retraining_zip() -> bytes:
    """Build an in-memory ZIP archive of all uploaded images organized by class_name/image.jpg + manifest.csv for retraining."""
    init_db()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        csv_buf = io.StringIO()
        csv_buf.write("\ufeff")
        writer = csv.writer(csv_buf)
        writer.writerow([
            "id", "created_at", "final_training_label", "predicted_class", "verified_label",
            "confidence", "margin_score", "is_uncertain", "width", "height",
            "blur_score", "brightness_score", "green_ratio", "quality_flag",
            "model_used", "client_ip", "geo_city", "developer_notes", "zip_path"
        ])

        with sqlite3.connect(str(DB_PATH)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM uploaded_images ORDER BY id DESC").fetchall()
            for r in rows:
                img_id = r["id"]
                final_label = (r["verified_label"] or r["predicted_class"] or "Unknown").strip()
                safe_folder = "".join(c if c.isalnum() or c in ("_", "-", ".") else "_" for c in final_label) or "Unknown"
                ext = Path(r["filename"] or "img.jpg").suffix or ".jpg"
                zip_rel_path = f"dataset/{safe_folder}/img_{img_id:05d}{ext}"

                img_bytes = bytes(r["image_blob"]) if r["image_blob"] else b""
                if not img_bytes and r["file_path"] and os.path.exists(r["file_path"]):
                    img_bytes = Path(r["file_path"]).read_bytes()

                if img_bytes:
                    zf.writestr(zip_rel_path, img_bytes)

                writer.writerow([
                    img_id, r["created_at"], final_label, r["predicted_class"], r["verified_label"],
                    r["confidence"], r["margin_score"], r["is_uncertain"], r["width"], r["height"],
                    r["blur_score"], r["brightness_score"], r["green_ratio"], r["quality_flag"],
                    r["model_used"], r["client_ip"], r["geo_city"], r["developer_notes"], zip_rel_path
                ])

        zf.writestr("dataset/manifest_metadata.csv", csv_buf.getvalue().encode("utf-8"))

    return buf.getvalue()


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


def get_developer_analytics(limit: int = 100) -> Dict[str, Any]:
    """Return full telemetry, KPIs, Active Learning stats, Knowledge Gaps, Peak Hours, and detailed logs."""
    init_db()
    with sqlite3.connect(str(DB_PATH)) as conn:
        conn.row_factory = sqlite3.Row

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
            SELECT CASE WHEN topic_category = '' OR topic_category IS NULL THEN '🌾 استشارة عامة' ELSE topic_category END AS topic,
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

        # 7. Registered Users Table (with activity counts)
        user_rows = conn.execute(
            """
            SELECT u.id, u.created_at, u.last_login_at, u.full_name, u.identifier,
                   u.phone, u.email, u.governorate, u.primary_crop, u.role,
                   u.login_count, u.client_ip, u.device_type, u.geo_city,
                   (SELECT COUNT(*) FROM uploaded_images img WHERE img.user_id = u.id) AS images_count,
                   (SELECT COUNT(*) FROM chat_logs ch WHERE ch.user_id = u.id) AS chats_count
            FROM users u
            ORDER BY u.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        registered_users = [dict(r) for r in user_rows]

        # 8. Recent Chat Logs
        chat_rows = conn.execute(
            """
            SELECT id, created_at, client_ip, device_type, session_id, location, crop,
                   rag_engine, user_query, bot_answer, sources_json, confidence,
                   latency_ms, status, error_message, topic_category, is_knowledge_gap,
                   geo_city, isp, user_id, user_name, user_identifier
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
            recent_chats.append(d)

        # 9. Recent Uploaded Images (with forensics, active learning & user attribution fields)
        img_rows = conn.execute(
            """
            SELECT id, created_at, filename, content_type, file_path, sha256_hash,
                   source_endpoint, model_used, predicted_class, predicted_class_ar,
                   confidence, top_predictions_json, user_query, rag_advice,
                   client_ip, device_type, latency_ms, width, height, file_size_kb,
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
        },
        "peak_hours": peak_hours,
        "top_chat_crops": top_chat_crops,
        "top_chat_topics": top_chat_topics,
        "top_diseases": top_diseases,
        "devices_breakdown": devices_breakdown,
        "top_visitors": top_visitors,
        "registered_users": registered_users,
        "recent_chats": recent_chats,
        "recent_images": recent_images,
        "recent_visits": recent_visits,
        "recent_errors": recent_errors,
    }


def backfill_existing_records() -> None:
    """Backfill forensics, uncertainty margin, and chat topics for any previously saved records."""
    init_db()
    with sqlite3.connect(str(DB_PATH)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, image_blob, top_predictions_json, confidence FROM uploaded_images WHERE width = 0 OR width IS NULL"
        ).fetchall()
        for r in rows:
            if r["image_blob"]:
                f = analyze_image_forensics(bytes(r["image_blob"]))
                tops = json.loads(r["top_predictions_json"] or "[]")
                _, margin, unc = compute_uncertainty_metrics(tops, r["confidence"])
                conn.execute(
                    """
                    UPDATE uploaded_images
                    SET width=?, height=?, file_size_kb=?, blur_score=?, brightness_score=?,
                        green_ratio=?, quality_flag=?, exif_camera=?, margin_score=?, is_uncertain=?
                    WHERE id=?
                    """,
                    (
                        f["width"], f["height"], f["file_size_kb"], f["blur_score"],
                        f["brightness_score"], f["green_ratio"], f["quality_flag"],
                        f["exif_camera"], margin, unc, r["id"],
                    ),
                )

        c_rows = conn.execute(
            "SELECT id, user_query, bot_answer, confidence FROM chat_logs WHERE topic_category = '' OR topic_category IS NULL"
        ).fetchall()
        for cr in c_rows:
            topic, is_gap = classify_chat_topic_and_gap(cr["user_query"], cr["bot_answer"], float(cr["confidence"] or 0.0))
            conn.execute(
                "UPDATE chat_logs SET topic_category=?, is_knowledge_gap=? WHERE id=?",
                (topic, is_gap, cr["id"]),
            )
        conn.commit()
        print(f"Backfilled {len(rows)} images and {len(c_rows)} chats.")


if __name__ == "__main__":
    backfill_existing_records()

