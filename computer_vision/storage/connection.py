"""Database Connection Management & Schema Migrations.

Provides thread-safe connection pooling / context manager, WAL mode configuration,
and schema initialization with backward-compatible migrations.
"""

from __future__ import annotations

import contextlib
import datetime
import logging
import os
import sqlite3
from pathlib import Path
from typing import Generator

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "predictions_history.db"
IMAGES_DIR = DATA_DIR / "uploaded_images"

_DB_INITIALIZED = False


def _ensure_column(
    conn: sqlite3.Connection, table: str, column: str, col_def: str
) -> None:
    """Safely add a column to an existing SQLite table if it does not exist."""
    cur = conn.execute(f"PRAGMA table_info({table})")
    existing = {row[1] for row in cur.fetchall()}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_def}")


@contextlib.contextmanager
def get_db_connection(
    timeout: float = 15.0,
) -> Generator[sqlite3.Connection, None, None]:
    """Provide a thread-safe context manager for SQLite connections with Row factory."""
    init_db()
    conn = sqlite3.connect(str(DB_PATH), timeout=timeout)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(force: bool = False) -> None:
    """Initialize SQLite database in high-concurrency WAL mode and private images folder."""
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
            ("prompt_tokens", "INTEGER DEFAULT 0"),
            ("completion_tokens", "INTEGER DEFAULT 0"),
            ("total_tokens", "INTEGER DEFAULT 0"),
            ("api_key_masked", "TEXT DEFAULT ''"),
            ("llm_model", "TEXT DEFAULT ''"),
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
            ("gps_lat", "REAL DEFAULT NULL"),
            ("gps_lon", "REAL DEFAULT NULL"),
            ("location_source", "TEXT DEFAULT 'manual'"),
            ("last_visitor_id", "TEXT DEFAULT ''"),
            ("auth_provider", "TEXT DEFAULT 'password'"),
            ("avatar_url", "TEXT DEFAULT ''"),
        ]:
            _ensure_column(conn, "users", col, cdef)

        # 6. Persistent Cookie Visitor Profiles Table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS visitor_profiles (
                visitor_id TEXT PRIMARY KEY,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                user_id INTEGER DEFAULT NULL,
                user_name TEXT DEFAULT '',
                user_identifier TEXT DEFAULT '',
                pinned_governorate TEXT DEFAULT '',
                gps_lat REAL DEFAULT NULL,
                gps_lon REAL DEFAULT NULL,
                location_source TEXT DEFAULT 'ip',
                primary_crop TEXT DEFAULT '',
                farm_size_feddan REAL DEFAULT 1.0,
                irrigation_type TEXT DEFAULT 'غمر',
                last_ip TEXT DEFAULT '',
                ip_city TEXT DEFAULT '',
                isp TEXT DEFAULT '',
                device_type TEXT DEFAULT '',
                browser_os TEXT DEFAULT '',
                visit_count INTEGER DEFAULT 1
            )
            """
        )

        # 7. AI Model, Token & API Key Consumption Telemetry Table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS llm_token_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                hour_bucket TEXT NOT NULL,
                service_type TEXT NOT NULL,
                endpoint TEXT DEFAULT '',
                model_name TEXT NOT NULL,
                api_key_masked TEXT DEFAULT '',
                prompt_tokens INTEGER DEFAULT 0,
                completion_tokens INTEGER DEFAULT 0,
                total_tokens INTEGER DEFAULT 0,
                estimated_cost_usd REAL DEFAULT 0.0,
                latency_ms REAL DEFAULT 0.0,
                status TEXT DEFAULT 'success',
                user_id INTEGER DEFAULT NULL,
                user_name TEXT DEFAULT '',
                visitor_hash TEXT DEFAULT '',
                client_ip TEXT DEFAULT '',
                request_preview TEXT DEFAULT ''
            )
            """
        )

        # 8. Leaf Recovery & Before/After Comparison Table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS followup_evaluations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                original_image_id INTEGER NOT NULL,
                followup_image_id INTEGER NOT NULL,
                days_since_treatment INTEGER DEFAULT 7,
                applied_treatment TEXT DEFAULT '',
                original_disease TEXT NOT NULL,
                current_disease TEXT NOT NULL,
                recovery_status TEXT NOT NULL,
                recovery_score_percent REAL DEFAULT 0.0,
                clinical_comparison_ar TEXT DEFAULT '',
                recommended_action_ar TEXT DEFAULT ''
            )
            """
        )

        # 9. Real-Time Cyber Security Incidents & Intrusion Detection Table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS security_incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                client_ip TEXT NOT NULL,
                incident_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                payload_preview TEXT DEFAULT '',
                action_taken TEXT NOT NULL,
                user_agent TEXT DEFAULT ''
            )
            """
        )

        # 10. Performance B-Tree Indexes
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_chat_logs_user_id ON chat_logs(user_id);"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_chat_logs_session_id ON chat_logs(session_id);"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_chat_logs_visitor_hash ON chat_logs(visitor_hash);"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_chat_logs_created_at ON chat_logs(created_at);"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_uploaded_images_user_id ON uploaded_images(user_id);"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_uploaded_images_visitor_hash ON uploaded_images(visitor_hash);"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_uploaded_images_created_at ON uploaded_images(created_at);"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_visitor_logs_visitor_hash ON visitor_logs(visitor_hash);"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_visitor_logs_created_at ON visitor_logs(created_at);"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_llm_token_logs_user_id ON llm_token_logs(user_id);"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_llm_token_logs_created_at ON llm_token_logs(created_at);"
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_users_phone ON users(phone);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_security_incidents_client_ip ON security_incidents(client_ip);"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_security_incidents_created_at ON security_incidents(created_at);"
        )

        # Seed default Admin Developer account if none exists
        admin_exists = conn.execute(
            "SELECT id FROM users WHERE role = 'admin' LIMIT 1"
        ).fetchone()
        if not admin_exists:
            from computer_vision.storage.utils import hash_password

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


def backfill_existing_records() -> None:
    """Utility to re-analyze existing stored images and calculate missing forensic metrics."""
    init_db()
    with sqlite3.connect(str(DB_PATH), timeout=15.0) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, image_blob FROM uploaded_images WHERE width = 0 OR file_size_kb = 0.0"
        ).fetchall()
        from computer_vision.storage.utils import analyze_image_forensics

        for r in rows:
            blob = r["image_blob"]
            if not blob:
                continue
            f = analyze_image_forensics(blob)
            conn.execute(
                """
                UPDATE uploaded_images
                SET width = ?, height = ?, file_size_kb = ?, blur_score = ?,
                    brightness_score = ?, green_ratio = ?, quality_flag = ?, exif_camera = ?
                WHERE id = ?
                """,
                (
                    f["width"],
                    f["height"],
                    f["file_size_kb"],
                    f["blur_score"],
                    f["brightness_score"],
                    f["green_ratio"],
                    f["quality_flag"],
                    f["exif_camera"],
                    r["id"],
                ),
            )
        conn.commit()
