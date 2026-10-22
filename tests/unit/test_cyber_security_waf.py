"""Comprehensive Cyber Attack Fortification and WAF Security Tests.

Explicitly validates protection against:
1. Automated Vulnerability Scanners (sqlmap, nikto, dirbuster, acunetix).
2. Honeypot Trap Traversal (active deception banning attackers seeking .env, .git, wp-admin).
3. Path Traversal & Local File Inclusion (LFI: ../, /etc/passwd, win.ini).
4. SQL Injection (SQLi: UNION SELECT, OR 1=1, SLEEP()).
5. Remote Code Execution (RCE) & Shell Command Chaining (; cat, $(whoami), | sh).
6. Server-Side Request Forgery (SSRF targeting cloud metadata 169.254.169.254).
7. Cross-Site Scripting (XSS payloads in query strings).
8. Adaptive IP Banlist Jail (Automatic ban, early drop, unban administration).
9. Real-time Security Incidents Audit Trail (/api/dev/security-incidents).
10. Legitimate Traffic Transparency (0 false positives on valid agricultural queries).
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import DEV_SECRET_KEY
from app.core.ip_banlist import (
    ban_ip,
    is_ip_banned,
    reset_banlist_for_testing,
)
from app.main import app

client = TestClient(app)


def setup_function():
    """Reset banlist before each test."""
    reset_banlist_for_testing()


def teardown_function():
    """Clean up banlist after each test."""
    reset_banlist_for_testing()


# ─── 1. Automated Vulnerability Scanner Mitigation ────────────────────────────


def test_waf_blocks_sqlmap_scanner_and_bans_ip():
    """Verify requests with sqlmap user-agent are blocked and IP is banned."""
    attacker_ip = "198.51.100.11"
    headers = {
        "User-Agent": "sqlmap/1.5.11#stable (http://sqlmap.org)",
        "X-Forwarded-For": attacker_ip,
    }

    # First attempt: WAF blocks scanner tool
    resp = client.get("/api/calculator/salinity", headers=headers)
    assert resp.status_code == 403
    assert resp.json()["code"] == "cyber_threat_blocked"

    # Verify IP was automatically placed in jail
    banned, remaining, reason = is_ip_banned(attacker_ip)
    assert banned is True
    assert remaining is not None and remaining > 3600
    assert "scanner" in reason.lower()

    # Subsequent normal request from same IP is immediately dropped
    clean_headers = {"X-Forwarded-For": attacker_ip, "User-Agent": "Mozilla/5.0"}
    resp_subsequent = client.get("/health", headers=clean_headers)
    assert resp_subsequent.status_code == 403
    assert "Retry-After" in resp_subsequent.headers


def test_waf_blocks_nikto_and_acunetix_scanners():
    """Verify Nikto and Acunetix web application scanners are rejected with 403."""
    for tool_ua in ("Nikto/2.1.6", "Acunetix-Web-Vulnerability-Scanner/13.0"):
        headers = {"User-Agent": tool_ua, "X-Forwarded-For": "203.0.113.44"}
        resp = client.get("/", headers=headers)
        assert resp.status_code == 403
        assert resp.json()["code"] == "cyber_threat_blocked"


# ─── 2. Honeypot Trap Traversal (Active Intrusion Deception) ───────────────────


def test_waf_honeypot_trap_env_file():
    """Verify accessing /.env triggers active honeypot defense and bans attacker."""
    attacker_ip = "192.0.2.77"
    headers = {"X-Forwarded-For": attacker_ip}

    resp = client.get("/.env", headers=headers)
    assert resp.status_code == 403
    assert resp.json()["code"] == "cyber_threat_blocked"

    # Attacker IP is jailed for 2 hours
    banned, remaining, _ = is_ip_banned(attacker_ip)
    assert banned is True
    assert remaining is not None and remaining > 3600


def test_waf_honeypot_trap_git_and_wp_admin():
    """Verify accessing /.git/config and /wp-admin traps and blocks the request."""
    for honeypot_url in ("/.git/config", "/wp-login.php", "/phpmyadmin", "/.aws/credentials"):
        headers = {"X-Forwarded-For": "192.0.2.88"}
        resp = client.get(honeypot_url, headers=headers)
        assert resp.status_code == 403
        assert resp.json()["code"] == "cyber_threat_blocked"


# ─── 3. Path Traversal & LFI/RFI Defenses ─────────────────────────────────────


def test_waf_blocks_path_traversal_lfi():
    """Verify directory traversal patterns (../../etc/passwd, boot.ini) are blocked."""
    headers = {"X-Forwarded-For": "198.51.100.99"}

    # Relative path escape
    resp1 = client.get("/api/chat?file=../../../../etc/passwd", headers=headers)
    assert resp1.status_code == 403

    # URL encoded traversal %2e%2e%2f
    resp2 = client.get("/static/%2e%2e/%2e%2e/win.ini", headers=headers)
    assert resp2.status_code == 403


# ─── 4. SQL Injection (SQLi) Defense ──────────────────────────────────────────


def test_waf_blocks_sqli_in_query_parameters():
    """Verify SQL injection payloads in query strings are blocked."""
    headers = {"X-Forwarded-For": "203.0.113.88"}

    # UNION SELECT exploit
    resp1 = client.get("/api/weather/today?crop=1%20UNION%20SELECT%20null,null,password%20FROM%20users--", headers=headers)
    assert resp1.status_code == 403

    # Boolean blind SQLi (' OR '1'='1)
    resp2 = client.get("/api/chat/memory?session_id=foo' OR '1'='1", headers=headers)
    assert resp2.status_code == 403

    # Time-based blind SQLi (SLEEP)
    resp3 = client.get("/api/calculator/salinity?crop=potato%27;%20SLEEP(5)--", headers=headers)
    assert resp3.status_code == 403


# ─── 5. Remote Code Execution (RCE) / Command Chaining ────────────────────────


def test_waf_blocks_rce_command_injection():
    """Verify OS command chaining (; cat, $(whoami)) in URL queries is blocked."""
    headers = {"X-Forwarded-For": "198.51.100.123"}

    # Command chaining with semicolon
    resp1 = client.get("/api/weather/today?gov=Cairo; cat /etc/passwd", headers=headers)
    assert resp1.status_code == 403

    # Subshell evaluation $(whoami)
    resp2 = client.get("/api/chat?query=$(whoami)", headers=headers)
    assert resp2.status_code == 403


# ─── 6. Server-Side Request Forgery (SSRF) Cloud Metadata ─────────────────────


def test_waf_blocks_ssrf_cloud_metadata_probe():
    """Verify AWS/Azure/GCP cloud metadata IP (169.254.169.254) in query is blocked."""
    headers = {"X-Forwarded-For": "198.51.100.200"}
    resp = client.get("/api/dev/backups?url=http://169.254.169.254/latest/meta-data/", headers=headers)
    assert resp.status_code == 403


# ─── 7. Cross-Site Scripting (XSS) in Query String ────────────────────────────


def test_waf_blocks_xss_in_query_parameters():
    """Verify XSS script and onerror injection in query parameters is blocked."""
    headers = {"X-Forwarded-For": "198.51.100.222"}
    resp = client.get("/api/calculator/tank-mix?crop=<script>alert('xss')</script>", headers=headers)
    assert resp.status_code == 403


# ─── 8. Adaptive Banlist & Administrative Unban ───────────────────────────────


def test_ip_banlist_manual_ban_and_unban_api():
    """Verify administrative unban endpoint lifts ban on jailed IPs."""
    test_ip = "198.51.100.55"
    ban_ip(test_ip, duration_seconds=600, reason="Penetration testing probe")

    # Confirm banned
    banned, _, _ = is_ip_banned(test_ip)
    assert banned is True

    # Active bans query via Dev API
    resp_incidents = client.get(f"/api/dev/security-incidents?key={DEV_SECRET_KEY}")
    assert resp_incidents.status_code == 200
    data = resp_incidents.json()
    assert test_ip in data["banned_ips"]

    # Unban IP via Dev API
    resp_unban = client.post(f"/api/dev/unban-ip?key={DEV_SECRET_KEY}&ip={test_ip}")
    assert resp_unban.status_code == 200
    assert resp_unban.json()["unbanned"] is True

    # Confirm no longer banned
    banned_after, _, _ = is_ip_banned(test_ip)
    assert banned_after is False


# ─── 9. Legitimate Traffic Transparency ───────────────────────────────────────


def test_legitimate_agricultural_requests_allowed():
    """Verify genuine farmers and valid agricultural requests pass cleanly without false positives."""
    clean_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }

    # 1. Health check
    resp_health = client.get("/health", headers=clean_headers)
    assert resp_health.status_code == 200

    # 2. Tank Mix Calculator
    resp_calc = client.post(
        "/api/calculator/tank-mix",
        json={
            "mode": "tank",
            "tanks_count": 1,
            "tank_type": "knapsack_20l",
            "dosage_rate": 50.0,
            "dosage_unit": "per_100l",
            "chemical_type": "liquid",
            "crop_category": "vegetable",
            "product_name": "مبيد فطري نحاسي",
        },
        headers=clean_headers,
    )
    assert resp_calc.status_code == 200

    # 3. Salinity Calculator
    resp_sal = client.post(
        "/api/calculator/salinity",
        json={
            "salinity_value": 800.0,
            "salinity_unit": "ppm",
            "crop_name": "طماطم",
            "irrigation_method": "تنقيط",
        },
        headers=clean_headers,
    )
    assert resp_sal.status_code == 200
