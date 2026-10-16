"""Automated SQLite Database Backup & WAL Snapshot Service.

Provides safe, online WAL backup using sqlite3.Connection.backup(),
gzip compression, automated rotation, and dev telemetry export.
"""

from __future__ import annotations

import datetime
import gzip
import logging
import shutil
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from computer_vision.storage.connection import DATA_DIR, DB_PATH, init_db

logger = logging.getLogger(__name__)

BACKUPS_DIR = DATA_DIR / "backups"


def _ensure_backups_dir() -> Path:
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    return BACKUPS_DIR


def perform_sqlite_backup(retention_count: int = 10) -> Dict[str, Any]:
    """Perform a live, non-blocking online backup of the SQLite database.
    
    Uses SQLite's online backup API (safe with WAL mode active),
    then compresses the snapshot into a .db.gz archive and rotates old backups.
    """
    init_db()
    if not DB_PATH.exists():
        return {
            "success": False,
            "error": "Source database file does not exist",
            "filename": "",
            "size_bytes": 0,
        }

    _ensure_backups_dir()
    now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    temp_raw_backup = BACKUPS_DIR / f"_temp_backup_{now_str}.db"
    final_gz_name = f"predictions_history_backup_{now_str}.db.gz"
    final_gz_path = BACKUPS_DIR / final_gz_name

    try:
        # Step 1: Safe online backup without locking writes
        src_conn = sqlite3.connect(str(DB_PATH), timeout=30.0)
        dest_conn = sqlite3.connect(str(temp_raw_backup))
        try:
            with dest_conn:
                src_conn.backup(dest_conn, pages=100)
        finally:
            dest_conn.close()
            src_conn.close()

        # Step 2: Gzip compression to minimize disk footprint
        with open(temp_raw_backup, "rb") as f_in:
            with gzip.open(final_gz_path, "wb", compresslevel=9) as f_out:
                shutil.copyfileobj(f_in, f_out)

        # Remove temp raw uncompressed file
        if temp_raw_backup.exists():
            temp_raw_backup.unlink()

        size_bytes = final_gz_path.stat().st_size
        size_kb = round(size_bytes / 1024, 2)
        size_mb = round(size_bytes / (1024 * 1024), 2)

        # Step 3: Rotate old backups keeping retention_count
        _rotate_old_backups(retention_count=retention_count)

        logger.info(f"SQLite backup successful: {final_gz_name} ({size_kb} KB)")

        try:
            from app.services.telegram_service import dispatch_telegram_alert_fire_and_forget
            dispatch_telegram_alert_fire_and_forget(
                title="نسخة احتياطية لقاعدة البيانات 💾",
                message=f"تم بنجاح إنشاء وأرشفة نسخة احتياطية مضغوطة لقاعدة البيانات:\n• الملف: <code>{final_gz_name}</code>\n• الحجم: <b>{size_kb} KB</b>",
                level="backup",
            )
        except Exception:
            pass

        return {
            "success": True,
            "filename": final_gz_name,
            "size_bytes": size_bytes,
            "size_kb": size_kb,
            "size_mb": size_mb,
            "created_at": datetime.datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"SQLite backup failed: {e}")
        if temp_raw_backup.exists():
            try:
                temp_raw_backup.unlink()
            except Exception:
                pass
        return {
            "success": False,
            "error": str(e),
            "filename": "",
            "size_bytes": 0,
        }


def _rotate_old_backups(retention_count: int = 10) -> None:
    """Keep only the latest retention_count backup archives."""
    try:
        backups = sorted(
            BACKUPS_DIR.glob("predictions_history_backup_*.db.gz"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if len(backups) > retention_count:
            for old_backup in backups[retention_count:]:
                try:
                    old_backup.unlink()
                    logger.info(f"Rotated old backup: {old_backup.name}")
                except Exception as ex:
                    logger.warning(f"Could not delete old backup {old_backup}: {ex}")
    except Exception as e:
        logger.warning(f"Rotation error: {e}")


def list_backups() -> List[Dict[str, Any]]:
    """List all available SQLite database backups sorted newest first."""
    _ensure_backups_dir()
    results = []
    try:
        files = sorted(
            BACKUPS_DIR.glob("predictions_history_backup_*.db.gz"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for f in files:
            stat = f.stat()
            results.append({
                "filename": f.name,
                "size_bytes": stat.st_size,
                "size_kb": round(stat.st_size / 1024, 2),
                "size_mb": round(stat.st_size / (1024 * 1024), 2),
                "created_at": datetime.datetime.fromtimestamp(stat.st_mtime).isoformat(),
            })
    except Exception as e:
        logger.error(f"Error listing backups: {e}")
    return results


def get_backup_file_path(filename: str) -> Optional[Path]:
    """Safely validate and return path to backup file, preventing directory traversal."""
    _ensure_backups_dir()
    clean_name = Path(filename).name  # Strips any directory traversal attempts
    target_path = BACKUPS_DIR / clean_name
    if target_path.exists() and target_path.is_file() and clean_name.endswith(".db.gz"):
        return target_path
    return None
