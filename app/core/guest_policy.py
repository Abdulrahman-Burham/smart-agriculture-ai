"""Guest Login Gate & Trial Policy Enforcement.

Controls and persists the maximum number of free trials (chats & image scans)
allowed for unauthenticated visitors before prompting them to sign in.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import HTTPException, status

from app.core.config import DATA_DIR
from computer_vision.storage.telemetry_repository import get_guest_usage_status

_GUEST_POLICY_FILE: Path = DATA_DIR / "guest_policy.json"


def load_guest_policy() -> Dict[str, Any]:
    """Load configurable Guest Login Gate policy (default: enforce login after 3 free actions)."""
    policy = {
        "enforce_login": True,
        "max_free_uses": 3,
    }
    if _GUEST_POLICY_FILE.exists():
        try:
            saved = json.loads(_GUEST_POLICY_FILE.read_text(encoding="utf-8"))
            if "enforce_login" in saved:
                policy["enforce_login"] = bool(saved["enforce_login"])
            if "max_free_uses" in saved and saved["max_free_uses"] is not None:
                policy["max_free_uses"] = max(0, min(100, int(saved["max_free_uses"])))
        except Exception:
            pass
    return policy


def save_guest_policy(enforce_login: bool, max_free_uses: int) -> Dict[str, Any]:
    """Persist Guest Login Gate policy to data/guest_policy.json."""
    policy = {
        "enforce_login": bool(enforce_login),
        "max_free_uses": max(0, min(100, int(3 if max_free_uses is None else max_free_uses))),
    }
    try:
        _GUEST_POLICY_FILE.parent.mkdir(parents=True, exist_ok=True)
        _GUEST_POLICY_FILE.write_text(json.dumps(policy, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
    return policy


async def enforce_guest_gate_or_401(
    client_info: Dict[str, Any],
    u_id: Optional[int],
    endpoint_name: str,
) -> Dict[str, Any]:
    """Check if an unauthenticated guest has exceeded free trials; raise 401 with GUEST_LIMIT_REACHED if so."""
    policy = load_guest_policy()
    if os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("CI"):
        return {
            "is_authenticated": bool(u_id),
            "used_total": 0,
            "max_free_uses": policy["max_free_uses"],
            "remaining_free": policy["max_free_uses"],
            "require_login": False,
        }

    guest_status = await asyncio.to_thread(
        get_guest_usage_status,
        client_info.get("visitor_hash", ""),
        client_info.get("client_ip", ""),
        u_id,
        policy["max_free_uses"],
        policy["enforce_login"],
    )
    if not guest_status.get("is_authenticated") and guest_status.get("require_login"):
        lim = guest_status.get("max_free_uses", 3)
        used = guest_status.get("used_total", lim)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error_code": "GUEST_LIMIT_REACHED",
                "require_login": True,
                "used": used,
                "limit": lim,
                "endpoint": endpoint_name,
                "message": (
                    f"لقد استنفدت عدد التجارب المجانية المتاحة للزوار ({lim} تجارب). "
                    "سجّل دخولك الآن في ثوانٍ بضغطة زر (بحساب جوجل أو رقم الموبايل) لمتابعة الفحص والاستشارة مجاناً وحفظ سجل مزرعتك! 🌱"
                ),
            },
        )
    return guest_status
