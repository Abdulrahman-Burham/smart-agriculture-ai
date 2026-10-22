"""Telegram Admin Webhook & Real-Time Production Alerting Service.

Enables instant notifications for:
- Severe 500 system errors and crash traces.
- High-risk epidemiological crop disease detections (e.g. Late blight >90%).
- Automated database backup completions.
- Security rate-limit bursts.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

from app.core.config import DATA_DIR

logger = logging.getLogger(__name__)

_TELEGRAM_CONFIG_FILE: Path = DATA_DIR / "telegram_config.json"


def load_telegram_config() -> Dict[str, Any]:
    """Load configurable Telegram Bot settings from JSON file or environment variables."""
    cfg = {
        "enabled": False,
        "bot_token": os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        "chat_id": os.environ.get("TELEGRAM_CHAT_ID", ""),
    }
    if _TELEGRAM_CONFIG_FILE.exists():
        try:
            saved = json.loads(_TELEGRAM_CONFIG_FILE.read_text(encoding="utf-8"))
            if "bot_token" in saved and saved["bot_token"]:
                cfg["bot_token"] = str(saved["bot_token"]).strip()
            if "chat_id" in saved and saved["chat_id"]:
                cfg["chat_id"] = str(saved["chat_id"]).strip()
            if "enabled" in saved:
                cfg["enabled"] = bool(saved["enabled"])
            elif cfg["bot_token"] and cfg["chat_id"]:
                cfg["enabled"] = True
        except Exception as e:
            logger.warning(f"Error reading telegram_config.json: {e}")
    elif cfg["bot_token"] and cfg["chat_id"]:
        cfg["enabled"] = True
    return cfg


def save_telegram_config(
    bot_token: str, chat_id: str, enabled: bool = True
) -> Dict[str, Any]:
    """Persist Telegram alert configuration to data/telegram_config.json."""
    cfg = {
        "enabled": bool(enabled),
        "bot_token": str(bot_token or "").strip(),
        "chat_id": str(chat_id or "").strip(),
    }
    try:
        _TELEGRAM_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        _TELEGRAM_CONFIG_FILE.write_text(
            json.dumps(cfg, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as e:
        logger.error(f"Error saving telegram_config.json: {e}")
    return cfg


def _send_sync_telegram_message(bot_token: str, chat_id: str, text: str) -> bool:
    """Send an HTTP POST message to Telegram Bot API synchronously."""
    if not bot_token or not chat_id or not text:
        return False
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=8.0) as resp:
            return resp.status == 200
    except Exception as e:
        logger.warning(f"Telegram alert delivery failed: {e}")
        return False


async def send_telegram_alert(
    title: str,
    message: str,
    level: str = "info",
    details: Optional[Dict[str, Any]] = None,
) -> bool:
    """Asynchronously dispatch an alert to the administrator's Telegram chat."""
    cfg = load_telegram_config()
    if not cfg.get("enabled") or not cfg.get("bot_token") or not cfg.get("chat_id"):
        return False

    icon = "ℹ️"
    if level == "danger":
        icon = "🚨"
    elif level == "warning":
        icon = "⚠️"
    elif level == "epidemic":
        icon = "🌾"
    elif level == "backup":
        icon = "💾"

    text = f"{icon} <b>[الخبير الزراعي] {title}</b>\n\n{message}"
    if details:
        text += "\n\n<b>التفاصيل:</b>"
        for k, v in details.items():
            text += f"\n• <b>{k}:</b> {v}"

    try:
        # Run delivery in background thread to prevent blocking FastAPI worker
        return await asyncio.to_thread(
            _send_sync_telegram_message,
            bot_token=cfg["bot_token"],
            chat_id=cfg["chat_id"],
            text=text,
        )
    except Exception as e:
        logger.warning(f"send_telegram_alert async exception: {e}")
        return False


def dispatch_telegram_alert_fire_and_forget(
    title: str,
    message: str,
    level: str = "info",
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """Non-blocking fire-and-forget helper safe to call from synchronous logging contexts."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(send_telegram_alert(title, message, level, details))
        else:
            asyncio.run(send_telegram_alert(title, message, level, details))
    except Exception:
        # If no loop active, trigger in a background thread
        cfg = load_telegram_config()
        if cfg.get("enabled") and cfg.get("bot_token") and cfg.get("chat_id"):
            import threading

            icon = "🚨" if level == "danger" else "ℹ️"
            txt = f"{icon} <b>[الخبير الزراعي] {title}</b>\n\n{message}"
            threading.Thread(
                target=_send_sync_telegram_message,
                args=(cfg["bot_token"], cfg["chat_id"], txt),
                daemon=True,
            ).start()
