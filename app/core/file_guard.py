"""Hardened File Upload Guard & Magic Bytes Inspector.

Validates that uploaded files:
1. Do not exceed maximum file size (default 15 MB).
2. Have genuine binary magic bytes (JPEG, PNG, WEBP).
3. Do not contain embedded executable headers (ELF, PE MZ) or server script tags (PHP, script).
4. Do not exceed pixel safety limits (decompression bomb DoS protection).
5. Sanitizes EXIF metadata (GPS / serial numbers) to protect farmer privacy.
"""

from __future__ import annotations

import io
import logging
from typing import Optional, Tuple

from PIL import Image

logger = logging.getLogger(__name__)

# Security constraints
MAX_FILE_SIZE_BYTES: int = 15 * 1024 * 1024  # 15 MB
MAX_DIMENSION_PX: int = 8000  # Max 8000x8000 pixels
Image.MAX_IMAGE_PIXELS = 64_000_000  # 64 MegaPixels max to prevent decompression bombs

# Magic byte signatures
_JPEG_MAGIC = b"\xff\xd8\xff"
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_WEBP_RIFF = b"RIFF"
_WEBP_SUB = b"WEBP"

# Dangerous payload signatures
_DANGEROUS_SIGNATURES = [
    b"<?php",
    b"<script",
    b"eval(",
    b"base64_decode(",
    b"\x7fELF",  # Linux ELF executable
    b"MZ",  # Windows PE executable
]


def validate_image_upload(
    contents: bytes, filename: str = "upload.jpg"
) -> Tuple[bool, str, Optional[bytes]]:
    """Validate, sanitize, and verify image payload safety.

    Returns:
        (is_valid, error_reason_ar, sanitized_bytes_or_none)
    """
    if not contents or len(contents) == 0:
        return False, "ملف الصورة المرفوع فارغ تماماً.", None

    # 1. Size constraint
    if len(contents) > MAX_FILE_SIZE_BYTES:
        size_mb = len(contents) / (1024 * 1024)
        return (
            False,
            f"حجم الملف كبير جداً ({size_mb:.1f} ميجابايت). الحد الأقصى المسموح به هو 15 ميجابايت.",
            None,
        )

    # 2. Magic byte verification
    is_jpeg = contents.startswith(_JPEG_MAGIC)
    is_png = contents.startswith(_PNG_MAGIC)
    is_webp = contents.startswith(_WEBP_RIFF) and len(contents) > 12 and contents[8:12] == _WEBP_SUB

    if not (is_jpeg or is_png or is_webp):
        logger.warning(
            f"[Security] Rejected upload '{filename}': Invalid magic bytes signature."
        )
        return (
            False,
            "نوع الملف غير مدعوم أو تالف. يُسمح فقط برفع صور حقيقية بصيغ (JPEG, PNG, WEBP).",
            None,
        )

    # 3. Executable & Script Content Detection
    header_sample = contents[:2048]
    for sig in _DANGEROUS_SIGNATURES:
        if sig in header_sample:
            logger.warning(
                f"[Security] Malicious payload signature detected in upload '{filename}' ({sig})."
            )
            return (
                False,
                "تم رفض الملف لاحتوائه على ترويسة أو شفرة برمجية غير آمنة.",
                None,
            )

    # 4. Decompression Bomb & Integrity Verification with PIL
    try:
        stream = io.BytesIO(contents)
        with Image.open(stream) as img:
            img.verify()

        # Re-open for dimension inspection and EXIF stripping (verify() closes the file)
        stream.seek(0)
        with Image.open(stream) as img:
            width, height = img.size
            if width > MAX_DIMENSION_PX or height > MAX_DIMENSION_PX:
                return (
                    False,
                    f"أبعاد الصورة مفرطة جداً ({width}x{height} بكسل). الحد الأقصى المسموح به هو 8000x8000 بكسل.",
                    None,
                )

            # Strip EXIF GPS/metadata to ensure user privacy and safe clean storage
            clean_stream = io.BytesIO()
            clean_format = "PNG" if img.format == "PNG" else "JPEG"
            if clean_format == "JPEG" and img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            img.save(clean_stream, format=clean_format, quality=92)
            sanitized_bytes = clean_stream.getvalue()

        return True, "", sanitized_bytes

    except Image.DecompressionBombError:
        logger.warning(f"[Security] DecompressionBombError on upload '{filename}'.")
        return (
            False,
            "تم حظر الصورة لأنها تتجاوز حدود معالجة الذاكرة الآمنة (Decompression Bomb).",
            None,
        )
    except Exception as e:
        logger.warning(f"[Security] Corrupt image upload '{filename}': {e}")
        return False, "ملف الصورة تالف أو غير صالح للعرض والمعالجة.", None
