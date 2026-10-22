"""Unit Tests for Rate Limiter and Database Backup Service."""

import pytest
from starlette.requests import Request
from fastapi import HTTPException

from app.core.rate_limiter import RateLimiter
from computer_vision.storage.backup_service import (
    perform_sqlite_backup,
    list_backups,
    get_backup_file_path,
)


def make_mock_request(
    ip: str = "192.168.1.100", dev_key: str = "", user_id: str = ""
) -> Request:
    scope = {
        "type": "http",
        "client": (ip, 12345),
        "headers": [(b"host", b"localhost")],
        "query_string": f"key={dev_key}".encode() if dev_key else b"",
    }
    if user_id:
        scope["headers"].append((b"cookie", f"user_id={user_id}".encode()))
    return Request(scope)


def test_rate_limiter_allows_under_limit():
    limiter = RateLimiter(
        requests_per_minute=5, window_seconds=10.0, scope="test_under"
    )
    req = make_mock_request(ip="10.0.0.1")
    for _ in range(5):
        assert limiter(req) is True


def test_rate_limiter_blocks_over_limit():
    limiter = RateLimiter(requests_per_minute=3, window_seconds=10.0, scope="test_over")
    req = make_mock_request(ip="10.0.0.2")
    for _ in range(3):
        assert limiter(req) is True
    with pytest.raises(HTTPException) as exc_info:
        limiter(req)
    assert exc_info.value.status_code == 429
    assert exc_info.value.detail["error"] == "rate_limit_exceeded"


def test_rate_limiter_whitelists_dev_key():
    from app.core.config import DEV_SECRET_KEY

    limiter = RateLimiter(requests_per_minute=2, window_seconds=10.0, scope="test_dev")
    req = make_mock_request(ip="10.0.0.3", dev_key=DEV_SECRET_KEY)
    for _ in range(10):
        assert limiter(req) is True


def test_rate_limiter_whitelists_localhost():
    limiter = RateLimiter(
        requests_per_minute=1, window_seconds=10.0, scope="test_local"
    )
    req = make_mock_request(ip="127.0.0.1")
    for _ in range(5):
        assert limiter(req) is True


def test_backup_service_creation_and_listing():
    result = perform_sqlite_backup(retention_count=5)
    assert result["success"] is True
    assert result["filename"].endswith(".db.gz")
    assert result["size_bytes"] > 0

    backups = list_backups()
    assert len(backups) > 0
    assert any(b["filename"] == result["filename"] for b in backups)

    path = get_backup_file_path(result["filename"])
    assert path is not None
    assert path.exists()

    # Test path traversal protection
    assert get_backup_file_path("../../../etc/passwd") is None
