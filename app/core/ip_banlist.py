"""Adaptive IP Threat Intelligence & Automated Banlist Jail.

Maintains a dynamic, thread-safe memory jail for IP addresses caught engaging
in malicious scanning, honeypot access, SQL injection, RCE, or automated cyber attacks.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# Default durations
DEFAULT_BAN_DURATION_SECONDS: float = 7200.0  # 2 Hours temporary jail
REPEAT_OFFENDER_BAN_SECONDS: float = 86400.0  # 24 Hours ban

_lock = threading.Lock()
# IP -> {"expires_at": float, "reason": str, "incident_count": int, "banned_at": float}
_BANNED_IPS: Dict[str, Dict[str, Any]] = {}

# Whitelisted loopback and trusted diagnostic addresses
_WHITELISTED_IPS = {"127.0.0.1", "::1", "localhost"}


def is_ip_banned(client_ip: str) -> Tuple[bool, Optional[int], str]:
    """Check if an IP address is currently banned.

    Returns:
        (is_banned: bool, remaining_seconds: Optional[int], reason: str)
    """
    clean_ip = (client_ip or "").strip()
    if not clean_ip or clean_ip in _WHITELISTED_IPS:
        return False, None, ""

    now = time.time()
    with _lock:
        info = _BANNED_IPS.get(clean_ip)
        if not info:
            return False, None, ""

        if now >= info["expires_at"]:
            # Ban has expired
            _BANNED_IPS.pop(clean_ip, None)
            return False, None, ""

        remaining = int(info["expires_at"] - now)
        return True, remaining, info.get("reason", "Malicious activity detected")


def ban_ip(
    client_ip: str,
    duration_seconds: float = DEFAULT_BAN_DURATION_SECONDS,
    reason: str = "Cyber attack detected",
) -> int:
    """Ban an IP address for the specified duration.

    Returns the total number of recorded offenses for this IP.
    """
    clean_ip = (client_ip or "").strip()
    if not clean_ip or clean_ip in _WHITELISTED_IPS:
        return 0

    now = time.time()
    with _lock:
        existing = _BANNED_IPS.get(clean_ip)
        incident_count = (existing["incident_count"] + 1) if existing else 1

        # If repeat offender, escalate ban duration
        ban_time = REPEAT_OFFENDER_BAN_SECONDS if incident_count >= 3 else duration_seconds
        expires_at = now + ban_time

        _BANNED_IPS[clean_ip] = {
            "expires_at": expires_at,
            "banned_at": now,
            "reason": reason,
            "incident_count": incident_count,
            "duration": ban_time,
        }

        logger.warning(
            f"[CyberDefense] IP {clean_ip} BANNED for {int(ban_time)}s (Offense #{incident_count}). Reason: {reason}"
        )
        return incident_count


def unban_ip(client_ip: str) -> bool:
    """Manually unban an IP address."""
    clean_ip = (client_ip or "").strip()
    with _lock:
        return bool(_BANNED_IPS.pop(clean_ip, None))


def get_all_banned_ips() -> Dict[str, Dict[str, Any]]:
    """Return a dictionary of all currently active banned IPs."""
    now = time.time()
    active = {}
    with _lock:
        expired = []
        for ip, info in list(_BANNED_IPS.items()):
            if now >= info["expires_at"]:
                expired.append(ip)
            else:
                active[ip] = {
                    **info,
                    "remaining_seconds": int(info["expires_at"] - now),
                }
        for ip in expired:
            _BANNED_IPS.pop(ip, None)
    return active


def reset_banlist_for_testing() -> None:
    """Reset the banlist for clean unit test runs."""
    with _lock:
        _BANNED_IPS.clear()
