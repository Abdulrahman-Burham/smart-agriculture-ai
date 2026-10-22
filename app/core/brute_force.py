"""Brute-Force & Credential Stuffing Defense Shield.

Protects authentication endpoints (/api/auth/login, /api/auth/register) against
automated dictionary attacks, brute-force cracking, and credential stuffing.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Lockout policy configuration
MAX_FAILED_ATTEMPTS: int = 5
FAILURE_WINDOW_SECONDS: float = 300.0  # 5 minutes
LOCKOUT_DURATION_SECONDS: float = 600.0  # 10 minutes temporary lockout

_lock = threading.Lock()
# key -> list of failed timestamp floats
_FAILED_ATTEMPTS: Dict[str, List[float]] = {}
# key -> lockout expiration timestamp float
_LOCKED_KEYS: Dict[str, float] = {}


def _clean_stale_entries(now: float) -> None:
    """Evict expired lockout entries and timestamps older than FAILURE_WINDOW_SECONDS."""
    # Evict expired lockouts
    expired_locks = [k for k, exp in _LOCKED_KEYS.items() if now > exp]
    for k in expired_locks:
        _LOCKED_KEYS.pop(k, None)

    # Evict stale attempt timestamps
    stale_keys = []
    cutoff = now - FAILURE_WINDOW_SECONDS
    for k, timestamps in _FAILED_ATTEMPTS.items():
        _FAILED_ATTEMPTS[k] = [t for t in timestamps if t >= cutoff]
        if not _FAILED_ATTEMPTS[k]:
            stale_keys.append(k)
    for k in stale_keys:
        _FAILED_ATTEMPTS.pop(k, None)


def check_brute_force(identifier: str, client_ip: str) -> Optional[int]:
    """Check if the client IP or user identifier is currently locked out.

    Returns the remaining lockout time in seconds if blocked, or None if allowed.
    """
    now = time.time()
    with _lock:
        _clean_stale_entries(now)

        clean_id = (identifier or "").strip().lower()
        clean_ip = (client_ip or "").strip()

        # Check IP lockout
        if clean_ip in _LOCKED_KEYS:
            remaining = int(_LOCKED_KEYS[clean_ip] - now)
            if remaining > 0:
                return remaining
            _LOCKED_KEYS.pop(clean_ip, None)

        # Check identifier lockout
        if clean_id and clean_id in _LOCKED_KEYS:
            remaining = int(_LOCKED_KEYS[clean_id] - now)
            if remaining > 0:
                return remaining
            _LOCKED_KEYS.pop(clean_id, None)

    return None


def record_failed_attempt(identifier: str, client_ip: str) -> Tuple[int, Optional[int]]:
    """Record a failed login attempt for the given identifier and IP.

    Returns (failure_count, lockout_seconds_remaining_if_locked).
    """
    now = time.time()
    clean_id = (identifier or "").strip().lower()
    clean_ip = (client_ip or "").strip()

    with _lock:
        _clean_stale_entries(now)

        # Track on IP
        ip_attempts = _FAILED_ATTEMPTS.setdefault(clean_ip, [])
        ip_attempts.append(now)

        # Track on Identifier
        id_attempts = _FAILED_ATTEMPTS.setdefault(clean_id, []) if clean_id else []
        if clean_id:
            id_attempts.append(now)

        cutoff = now - FAILURE_WINDOW_SECONDS
        recent_ip_fails = len([t for t in ip_attempts if t >= cutoff])
        recent_id_fails = len([t for t in id_attempts if t >= cutoff])

        max_fails = max(recent_ip_fails, recent_id_fails)

        # Trigger lockout if threshold reached
        if recent_ip_fails >= MAX_FAILED_ATTEMPTS:
            _LOCKED_KEYS[clean_ip] = now + LOCKOUT_DURATION_SECONDS
            logger.warning(
                f"[Security] IP {clean_ip} locked out for {LOCKOUT_DURATION_SECONDS}s after {recent_ip_fails} failed attempts."
            )
            return max_fails, int(LOCKOUT_DURATION_SECONDS)

        if clean_id and recent_id_fails >= MAX_FAILED_ATTEMPTS:
            _LOCKED_KEYS[clean_id] = now + LOCKOUT_DURATION_SECONDS
            logger.warning(
                f"[Security] Account {clean_id} locked out for {LOCKOUT_DURATION_SECONDS}s after {recent_id_fails} failed attempts."
            )
            return max_fails, int(LOCKOUT_DURATION_SECONDS)

        return max_fails, None


def record_successful_attempt(identifier: str, client_ip: str) -> None:
    """Clear failed attempt records upon successful login."""
    clean_id = (identifier or "").strip().lower()
    clean_ip = (client_ip or "").strip()

    with _lock:
        _FAILED_ATTEMPTS.pop(clean_ip, None)
        _LOCKED_KEYS.pop(clean_ip, None)
        if clean_id:
            _FAILED_ATTEMPTS.pop(clean_id, None)
            _LOCKED_KEYS.pop(clean_id, None)


def reset_brute_force_for_testing() -> None:
    """Reset all brute-force tracking structures (used in unit tests)."""
    with _lock:
        _FAILED_ATTEMPTS.clear()
        _LOCKED_KEYS.clear()
