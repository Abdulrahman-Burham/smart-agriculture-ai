"""Image Repository: Uploaded Leaf Images, Active Learning Signals, and Retraining Dataset Exports.

Manages private on-disk and SQLite binary BLOB storage for diagnostic images,
computes uncertainty margins for active learning, saves developer ground-truth verifications,
and builds downloadable Kaggle/PyTorch/TensorFlow retraining ZIP archives.
"""

from __future__ import annotations

import csv
import datetime
import hashlib
import io
import json
import os
import sqlite3
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from computer_vision.storage.connection import DB_PATH, IMAGES_DIR, init_db
from computer_vision.storage.utils import (
    analyze_image_forensics,
    compute_uncertainty_metrics,
    parse_user_agent,
    resolve_ip_geo,
)


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


def get_image_record_by_id(image_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve full diagnostic metadata by image ID for prescription generation."""
    init_db()
    with sqlite3.connect(str(DB_PATH)) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            """
            SELECT id, created_at, filename, content_type, model_used,
                   predicted_class, predicted_class_ar, confidence, top_predictions_json,
                   user_query, rag_advice, client_ip, geo_city, weather_snapshot,
                   user_id, user_name, user_identifier
            FROM uploaded_images
            WHERE id = ?
            """,
            (int(image_id),),
        )
        row = cur.fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            d["top_predictions"] = json.loads(d.get("top_predictions_json") or "[]")
        except Exception:
            d["top_predictions"] = []
        return d



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
            "model_used", "client_ip", "geo_city", "developer_notes", "zip_path",
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
                    r["model_used"], r["client_ip"], r["geo_city"], r["developer_notes"], zip_rel_path,
                ])

        zf.writestr("dataset/manifest_metadata.csv", csv_buf.getvalue().encode("utf-8"))

    return buf.getvalue()
