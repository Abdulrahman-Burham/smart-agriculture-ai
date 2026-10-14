"""Sliding-Window Rate Limiter & AI Anti-Abuse Protection.

Guards high-cost endpoints (CV Diagnosis, RAG Chat, STT, TTS) against
scraping, bot bursts, and denial-of-service while preserving a seamless experience
for genuine farmers and authenticated users.
"""

import collections
import logging
import time
from typing import Deque, Dict

from fastapi import HTTPException, Request, status

from app.core.config import DEV_SECRET_KEY

logger = logging.getLogger(__name__)

# Sliding window storage: client_identifier -> deque of request timestamps
_REQUEST_WINDOWS: Dict[str, Deque[float]] = collections.defaultdict(collections.deque)
_LAST_CLEANUP_TIME: float = time.time()
_CLEANUP_INTERVAL: float = 300.0  # Clean memory every 5 minutes


def _cleanup_stale_buckets(window_seconds: float = 60.0) -> None:
    """Periodically purge entries older than window_seconds to keep RAM footprint low."""
    global _LAST_CLEANUP_TIME
    now = time.time()
    if now - _LAST_CLEANUP_TIME < _CLEANUP_INTERVAL:
        return
    _LAST_CLEANUP_TIME = now
    stale_keys = []
    cutoff = now - window_seconds
    for key, timestamps in list(_REQUEST_WINDOWS.items()):
        while timestamps and timestamps[0] < cutoff:
            timestamps.popleft()
        if not timestamps:
            stale_keys.append(key)
    for key in stale_keys:
        _REQUEST_WINDOWS.pop(key, None)


class RateLimiter:
    """Sliding-window rate limiter configurable per endpoint or service type."""

    def __init__(
        self,
        requests_per_minute: int = 30,
        authenticated_requests_per_minute: int = 75,
        window_seconds: float = 60.0,
        scope: str = "general",
    ):
        self.requests_per_minute = requests_per_minute
        self.authenticated_requests_per_minute = authenticated_requests_per_minute
        self.window_seconds = window_seconds
        self.scope = scope

    def __call__(self, request: Request) -> bool:
        # 1. Whitelist local loopback and internal health checks
        client_ip = request.client.host if request.client else "unknown"
        if client_ip in ("127.0.0.1", "::1", "localhost"):
            return True

        # 2. Whitelist Developer Admin requests with valid key
        query_key = request.query_params.get("key") or request.headers.get("X-Dev-Key")
        if query_key and query_key == DEV_SECRET_KEY:
            return True

        # 3. Check authentication status
        user_id = request.cookies.get("user_id") or request.headers.get("X-User-Id")
        is_authenticated = bool(user_id)
        max_requests = (
            self.authenticated_requests_per_minute
            if is_authenticated
            else self.requests_per_minute
        )

        now = time.time()
        _cleanup_stale_buckets(self.window_seconds)

        # Unique key composed of scope + user/IP
        identifier = f"{self.scope}:{user_id if user_id else client_ip}"
        timestamps = _REQUEST_WINDOWS[identifier]

        # Evict timestamps outside the sliding window
        window_start = now - self.window_seconds
        while timestamps and timestamps[0] < window_start:
            timestamps.popleft()

        # Check rate limit
        if len(timestamps) >= max_requests:
            retry_after = int(self.window_seconds - (now - timestamps[0])) + 1
            logger.warning(
                f"Rate limit exceeded for {identifier} on scope {self.scope} "
                f"({len(timestamps)}/{max_requests} reqs/min). Retry after {retry_after}s"
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "rate_limit_exceeded",
                    "message": (
                        "⚠️ عذراً يا هندسة، تجاوزت الحد المسموح للطلبات السريعة لحماية موارد وسيرفر الذكاء الاصطناعي. "
                        f"يُرجى الانتظار {retry_after} ثانية والمحاولة مجدداً."
                    ),
                    "retry_after": retry_after,
                    "scope": self.scope,
                },
                headers={"Retry-After": str(retry_after)},
            )

        # Record this request timestamp
        timestamps.append(now)
        return True


# Pre-configured rate limiters for core endpoints
ai_diagnose_limiter = RateLimiter(
    requests_per_minute=25,
    authenticated_requests_per_minute=60,
    window_seconds=60.0,
    scope="ai_diagnose",
)

ai_chat_limiter = RateLimiter(
    requests_per_minute=30,
    authenticated_requests_per_minute=80,
    window_seconds=60.0,
    scope="ai_chat",
)

ai_audio_limiter = RateLimiter(
    requests_per_minute=30,
    authenticated_requests_per_minute=90,
    window_seconds=60.0,
    scope="ai_audio",
)
