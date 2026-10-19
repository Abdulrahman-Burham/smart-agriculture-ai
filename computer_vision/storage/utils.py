"""Storage Utilities: Security, Cryptography, Forensics, and Request Inspection.

Contains:
- PBKDF2-HMAC-SHA256 password hashing & verification
- Signed HMAC-SHA256 user authentication tokens
- Input validation & normalization for Egyptian mobile numbers and emails
- Forensics & Computer Vision quality metrics (Laplacian blur, brightness, HSV foliage ratio, EXIF)
- Active Learning uncertainty margin calculation
- Silent IP geolocation and User-Agent device categorization
- Token estimation and commercial Gemini API cost estimation
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import io
import json
import os
import re
import secrets
import time
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

try:
    import cv2
except Exception:
    cv2 = None  # type: ignore[assignment]
import numpy as np
from PIL import ExifTags, Image

AUTH_SECRET_KEY = os.environ.get("AGRI_AUTH_SECRET", "smart-agri-jwt-secret-abdo-2026-prod-key")

_IP_GEO_CACHE: Dict[str, Dict[str, Any]] = {}
_ARABIC_DIGITS_MAP = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")

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
        if len(email) > 120 or ".." in email or not _EMAIL_REGEX.match(email):
            return None, "صيغة البريد الإلكتروني غير صحيحة (مثال صحيح: name@gmail.com)."
        domain = email.split("@", 1)[1]
        if domain in ("example.com", "test.com", "mail.com", "localhost") or len(domain) < 4:
            return None, "يرجى إدخال بريد إلكتروني حقيقي وفعّال."
    else:
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

    cookies = getattr(request, "cookies", {}) or {}
    state_vid = getattr(getattr(request, "state", None), "visitor_id", "") or ""
    cookie_vid = (cookies.get("agri_vid") or state_vid).strip()
    if cookie_vid and len(cookie_vid) >= 6:
        visitor_hash = cookie_vid[:32]
    else:
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
        if cv2 is not None:
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

                hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
                b_ch = bgr[:, :, 0].astype(np.float32)
                g_ch = bgr[:, :, 1].astype(np.float32)
                mask_plant = (cv2.inRange(hsv, np.array([22, 28, 25]), np.array([92, 255, 255])) > 0) & (g_ch >= (b_ch - 4.0))
                green_pct = float(np.count_nonzero(mask_plant)) / float(max(1, h * w)) * 100.0
                metrics["green_ratio"] = round(green_pct, 1)

                issues = []
                if blur_val < 45.0:
                    issues.append("صورة مهزوزة/غير واضحة")
                if brightness_val < 40.0:
                    issues.append("إضاءة مظلمة")
                elif brightness_val > 225.0:
                    issues.append("إضاءة ساطعة جداً")
                if green_pct < 18.0:
                    issues.append("❌ نسبة نبات منخفضة جداً (غير صالحة للتشخيص)")
                elif green_pct < 25.0:
                    issues.append("⚠️ نسبة نبات ضعيفة (يُفضل تصوير الورقة عن قرب)")
                metrics["quality_flag"] = " ، ".join(issues) if issues else "✅ جودة ممتازة"
        else:
            pil_fallback = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            w, h = pil_fallback.size
            metrics["width"] = int(w)
            metrics["height"] = int(h)
            arr = np.array(pil_fallback, dtype=np.float32)
            r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
            bright = float(np.mean((r + g + b) / 3.0))
            metrics["brightness_score"] = round(bright, 1)
            plant_px = (g > (r + 4.0)) & (g >= (b + 2.0)) & (g > 35.0)
            green_pct = float(np.count_nonzero(plant_px)) / float(max(1, h * w)) * 100.0
            metrics["green_ratio"] = round(green_pct, 1)
            issues = []
            if bright < 40.0:
                issues.append("إضاءة مظلمة")
            elif bright > 225.0:
                issues.append("إضاءة ساطعة جداً")
            if green_pct < 18.0:
                issues.append("❌ نسبة نبات منخفضة جداً (غير صالحة للتشخيص)")
            elif green_pct < 25.0:
                issues.append("⚠️ نسبة نبات ضعيفة (يُفضل تصوير الورقة عن قرب)")
            metrics["quality_flag"] = " ، ".join(issues) if issues else "✅ جودة ممتازة"
    except Exception:
        pass

    try:
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


def mask_api_key(raw_key: str, key_index: Optional[int] = None) -> str:
    """Safely mask an API key (e.g. 'AIzaSyB...9xQ2 (#1)')."""
    k = (raw_key or "").strip()
    if not k or k in ("not-needed", "local", "edge-tts", "cache"):
        return k or "local-model"
    if "..." in k:
        return k
    masked = f"{k[:7]}...{k[-4:]}" if len(k) > 12 else f"{k[:3]}***"
    if key_index is not None and key_index >= 1:
        return f"Key #{key_index} ({masked})"
    return masked


def estimate_tokens(text: str) -> int:
    """Estimate LLM token count for Arabic/English text (approx 1 token per 2.8 Arabic chars)."""
    if not text:
        return 0
    s = str(text).strip()
    if not s:
        return 0
    return max(1, int(round(len(s) / 2.8)))


def estimate_gemini_cost_usd(model_name: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Estimate commercial API cost in USD based on standard Gemini Flash/Pro pricing per 1M tokens."""
    m = (model_name or "").lower()
    if "pro" in m:
        in_rate, out_rate = 1.25, 5.00
    elif "lite" in m:
        in_rate, out_rate = 0.075, 0.30
    elif "tts" in m:
        in_rate, out_rate = 0.15, 0.60
    else:
        in_rate, out_rate = 0.15, 0.60
    cost = ((max(0, int(prompt_tokens)) / 1_000_000.0) * in_rate) + (
        (max(0, int(completion_tokens)) / 1_000_000.0) * out_rate
    )
    return round(cost, 6)
