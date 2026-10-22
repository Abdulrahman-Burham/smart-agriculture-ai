"""Web Application Firewall (WAF) & Active Cyber Threat Shield.

Provides proactive, real-time cyber defense against:
1. Automated Vulnerability Scanners (sqlmap, nikto, acunetix, nmap, dirbuster, etc.).
2. Honeypot Trap Paths (Active deception banning attackers probing for .env, .git, wp-admin).
3. Path Traversal & Local/Remote File Inclusion (LFI/RFI: ../, /etc/passwd, file://).
4. SQL Injection (SQLi: UNION SELECT, SLEEP(), 1=1, DROP TABLE).
5. Remote Code Execution (RCE) and Command Chaining (| cat, ; wget, $(...), etc.).
6. Server-Side Request Forgery (SSRF targeting cloud metadata 169.254.169.254).
7. Cross-Site Scripting (XSS payloads in URL query strings and parameters).
8. Automated IP Banning & Threat Telemetry Logging.
"""

from __future__ import annotations

import json
import logging
import re
import urllib.parse
from typing import Set

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.ip_banlist import ban_ip, is_ip_banned
from computer_vision.storage.telemetry_repository import record_security_incident

logger = logging.getLogger(__name__)

# 1. Known Automated Exploitation & Reconnaissance Scanners
_SCANNER_USER_AGENTS = re.compile(
    r"\b(sqlmap|nikto|acunetix|nmap|masscan|zgrab|gobuster|dirbuster|wpscan|hydra|metasploit|burpsuite|netsparker|arachni|havij)\b",
    re.IGNORECASE,
)

# 2. Honeypot Trap Paths (Probe by bots looking for leaks/vulnerabilities)
_HONEYPOT_PATHS: Set[str] = {
    "/.env",
    "/.git",
    "/.git/config",
    "/.git/HEAD",
    "/wp-admin",
    "/wp-login.php",
    "/xmlrpc.php",
    "/phpmyadmin",
    "/pma",
    "/actuator",
    "/actuator/health",
    "/.aws",
    "/.aws/credentials",
    "/config.json",
    "/web.config",
    "/shell.php",
    "/id_rsa",
    "/admin.php",
}

# 3. Path Traversal / LFI Patterns
_PATH_TRAVERSAL_PATTERN = re.compile(
    r"(\.\.[/\\]|%2e%2e[/\\]|%2e%2e%2f|%2e%2e%5c|/etc/passwd|/etc/shadow|c:[/\\]boot\.ini|win\.ini|php://|file://)",
    re.IGNORECASE,
)

# 4. Deep SQL Injection Patterns in Query / Path
_SQLI_PATTERN = re.compile(
    r"(\bUNION\b\s+\bSELECT\b|(\bOR\b|\bAND\b)\s+['\"]?1['\"]?\s*=\s*['\"]?1|\bSLEEP\s*\(|\bBENCHMARK\s*\(|\bWAITFOR\s+DELAY\b|;\s*DROP\s+TABLE\b|;\s*DELETE\s+FROM\b)",
    re.IGNORECASE,
)

# 5. Remote Code Execution (RCE) / Shell Chaining Patterns
_RCE_PATTERN = re.compile(
    r"(;\s*(cat|ls|rm|wget|curl|nc|bash|sh|powershell|cmd\.exe)\b|\|\s*(cat|sh|bash|powershell)\b|\$\([^)]+\)|`[^`]+`)",
    re.IGNORECASE,
)

# 6. SSRF Cloud Metadata Exploit Patterns
_SSRF_PATTERN = re.compile(
    r"(169\.254\.169\.254|metadata\.google\.internal|100\.100\.100\.200)",
    re.IGNORECASE,
)

# 7. XSS Payload Pattern in URL/Query
_XSS_PATTERN = re.compile(
    r"(<\s*script\b|javascript\s*:|<\s*img\b[^>]+onerror\s*=|data:text/html|<\s*svg\b[^>]+onload\s*=)",
    re.IGNORECASE,
)

_JSON_BLOCK_CONTENT = json.dumps(
    {
        "status": "error",
        "code": "cyber_threat_blocked",
        "detail": "تم حظر هذا الاتصال تلقائياً بواسطة جدار الحماية السيبراني لحماية المنظومة الزراعية.",
    },
    ensure_ascii=False,
).encode("utf-8")


def _get_client_ip(request: Request) -> str:
    """Accurately extract client IP address prioritizing trusted proxy forwarding headers."""
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else "unknown"


class CyberSecurityWAFMiddleware(BaseHTTPMiddleware):
    """Deep Packet & Threat Inspection Web Application Firewall (WAF)."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        client_ip = _get_client_ip(request)
        path = request.url.path
        raw_query = request.url.query
        user_agent = request.headers.get("user-agent", "")

        # ── 1. Check if IP is in Active Banlist Jail ──────────────────────
        is_banned, remaining, reason = is_ip_banned(client_ip)
        if is_banned:
            logger.warning(
                f"[WAF] Dropped connection from banned IP {client_ip} (Remaining: {remaining}s, Reason: {reason})"
            )
            return Response(
                content=_JSON_BLOCK_CONTENT,
                status_code=403,
                media_type="application/json; charset=utf-8",
                headers={"Retry-After": str(remaining or 3600)},
            )

        # ── 2. Automated Vulnerability Scanner Mitigation ────────────────
        if user_agent and _SCANNER_USER_AGENTS.search(user_agent):
            logger.warning(
                f"[WAF] Blocked malicious scanner User-Agent from {client_ip}: {user_agent}"
            )
            ban_ip(client_ip, 7200, f"Malicious scanner tool ({user_agent[:40]})")
            record_security_incident(
                client_ip=client_ip,
                incident_type="automated_vulnerability_scanner",
                severity="critical",
                endpoint=path,
                payload_preview=user_agent,
                action_taken="banned_2h",
                user_agent=user_agent,
            )
            return Response(
                content=_JSON_BLOCK_CONTENT,
                status_code=403,
                media_type="application/json; charset=utf-8",
            )

        # ── 3. Honeypot Trap Detection (Active Deception) ────────────────
        lower_path = path.lower()
        if any(lower_path == hp or lower_path.startswith(hp + "/") for hp in _HONEYPOT_PATHS):
            logger.warning(
                f"[WAF] Honeypot trap triggered by {client_ip} on path '{path}'!"
            )
            ban_ip(client_ip, 7200, f"Honeypot trap accessed: {path}")
            record_security_incident(
                client_ip=client_ip,
                incident_type="honeypot_trap_hit",
                severity="critical",
                endpoint=path,
                payload_preview=path,
                action_taken="banned_2h",
                user_agent=user_agent,
            )
            return Response(
                content=_JSON_BLOCK_CONTENT,
                status_code=403,
                media_type="application/json; charset=utf-8",
            )

        # ── 4. Query & Path URL Decoded Inspection ───────────────────────
        decoded_path = urllib.parse.unquote(path)
        decoded_query = urllib.parse.unquote(raw_query)
        target_payload = f"{decoded_path}?{decoded_query}" if raw_query else decoded_path

        # 4.1 Path Traversal / LFI Check
        if _PATH_TRAVERSAL_PATTERN.search(target_payload):
            logger.warning(
                f"[WAF] Path Traversal attack from {client_ip} on '{target_payload}'"
            )
            ban_ip(client_ip, 3600, "Path traversal attempt")
            record_security_incident(
                client_ip=client_ip,
                incident_type="path_traversal",
                severity="high",
                endpoint=path,
                payload_preview=target_payload,
                action_taken="blocked_403",
                user_agent=user_agent,
            )
            return Response(
                content=_JSON_BLOCK_CONTENT,
                status_code=403,
                media_type="application/json; charset=utf-8",
            )

        # 4.2 SQL Injection in Query/Path Check
        if _SQLI_PATTERN.search(target_payload):
            logger.warning(
                f"[WAF] SQL Injection attack from {client_ip} on '{target_payload}'"
            )
            ban_ip(client_ip, 7200, "SQL injection payload")
            record_security_incident(
                client_ip=client_ip,
                incident_type="sqli_attack",
                severity="critical",
                endpoint=path,
                payload_preview=target_payload,
                action_taken="banned_2h",
                user_agent=user_agent,
            )
            return Response(
                content=_JSON_BLOCK_CONTENT,
                status_code=403,
                media_type="application/json; charset=utf-8",
            )

        # 4.3 Remote Code Execution (RCE) Check
        if _RCE_PATTERN.search(target_payload):
            logger.warning(
                f"[WAF] RCE Command Injection from {client_ip} on '{target_payload}'"
            )
            ban_ip(client_ip, 7200, "Remote code execution attempt")
            record_security_incident(
                client_ip=client_ip,
                incident_type="rce_attempt",
                severity="critical",
                endpoint=path,
                payload_preview=target_payload,
                action_taken="banned_2h",
                user_agent=user_agent,
            )
            return Response(
                content=_JSON_BLOCK_CONTENT,
                status_code=403,
                media_type="application/json; charset=utf-8",
            )

        # 4.4 SSRF Cloud Metadata Check
        if _SSRF_PATTERN.search(target_payload):
            logger.warning(
                f"[WAF] SSRF Cloud Metadata probing from {client_ip} on '{target_payload}'"
            )
            ban_ip(client_ip, 7200, "SSRF cloud metadata probe")
            record_security_incident(
                client_ip=client_ip,
                incident_type="ssrf_attempt",
                severity="critical",
                endpoint=path,
                payload_preview=target_payload,
                action_taken="banned_2h",
                user_agent=user_agent,
            )
            return Response(
                content=_JSON_BLOCK_CONTENT,
                status_code=403,
                media_type="application/json; charset=utf-8",
            )

        # 4.5 XSS Attack Check in Query
        if _XSS_PATTERN.search(decoded_query):
            logger.warning(
                f"[WAF] XSS payload in query from {client_ip}: '{decoded_query}'"
            )
            record_security_incident(
                client_ip=client_ip,
                incident_type="xss_attack",
                severity="high",
                endpoint=path,
                payload_preview=decoded_query,
                action_taken="blocked_403",
                user_agent=user_agent,
            )
            return Response(
                content=_JSON_BLOCK_CONTENT,
                status_code=403,
                media_type="application/json; charset=utf-8",
            )

        # ── 5. Payload Size & Anti-DoS Header Guard ──────────────────────
        if len(raw_query) > 2048:
            return Response(
                content=json.dumps({"detail": "URI query string exceeds maximum safe length."}).encode("utf-8"),
                status_code=414,
                media_type="application/json",
            )

        content_length = request.headers.get("content-length")
        if content_length:
            try:
                cl_val = int(content_length)
                # Standard non-file upload endpoints shouldn't send massive bodies
                is_upload_endpoint = any(
                    path.startswith(p) for p in ("/api/diagnose", "/api/dev")
                )
                max_allowed = 16 * 1024 * 1024 if is_upload_endpoint else 2 * 1024 * 1024
                if cl_val > max_allowed:
                    return Response(
                        content=json.dumps({"detail": "حجم حمولة الطلب يتجاوز الحد المسموح به لمنع هجمات حجب الخدمة."}).encode("utf-8"),
                        status_code=413,
                        media_type="application/json; charset=utf-8",
                    )
            except ValueError:
                pass

        # Forward request to next middleware / route handler
        return await call_next(request)
