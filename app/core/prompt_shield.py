"""AI Prompt Shield & Injection Firewall (OWASP LLM Top 10 Defenses).

Guards the Agricultural RAG and LLM diagnostic pipelines against:
1. Direct Prompt Injections and Jailbreaks (e.g., 'ignore previous instructions', 'DAN', 'system override').
2. System Prompt Exfiltration & Leakage attempts.
3. Arbitrary Code & OS Command Injection (e.g., eval, exec, subprocess, __import__).
4. Cross-Site Scripting (XSS) payloads embedded in chat queries.
5. SQL Injection syntax targeting database backends.
"""

from __future__ import annotations

import re
from typing import Tuple

# 1. Prompt Injection & Jailbreak Signatures (English & Arabic)
_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions|prompts|rules)", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?(previous|prior|above)\s+(instructions|prompts|rules)", re.IGNORECASE),
    re.compile(r"\byou\s+are\s+now\s+(DAN|unrestricted|jailbroken|freed)\b", re.IGNORECASE),
    re.compile(r"\b(jailbreak|system\s+override|prompt\s+injection)\b", re.IGNORECASE),
    re.compile(r"\b(reveal|print|output|display|show|leak)\s+(your\s+)?(system\s+prompt|initial\s+prompt|secret\s+instructions)\b", re.IGNORECASE),
    re.compile(r"\bwhat\s+(is|are)\s+your\s+(system\s+prompt|hidden\s+instructions|secret\s+rules)\b", re.IGNORECASE),
    re.compile(r"\bact\s+as\s+an?\s+unrestricted\s+AI\b", re.IGNORECASE),
    re.compile(r"تجاهل\s+(كل\s+)?(التعليمات|الأوامر|القواعد|السياسات)\s+(السابقة|الأصلية)", re.IGNORECASE),
    re.compile(r"(اكشف|اظهر|اطبع|اعطني|هات)\s+(نص\s+)?(التعليمات\s+المخفية|السيستم\s+برومبت|الأوامر\s+السرية|مفتاح\s+النظام)", re.IGNORECASE),
    re.compile(r"(تجاوز|الغاء)\s+(كل\s+)?(قواعد\s+الأمان|القيود)", re.IGNORECASE),
]

# 2. Remote Code / OS Command Injection Signatures
_CODE_INJECTION_PATTERNS = [
    re.compile(r"\b(eval|exec|compile|__import__|getattr)\s*\(", re.IGNORECASE),
    re.compile(r"\b(os\.system|subprocess\.|shutil\.|pty\.)", re.IGNORECASE),
    re.compile(r"\b(rm\s+-rf|curl\s+https?://|wget\s+https?://|bash\s+-i|nc\s+-e)\b", re.IGNORECASE),
]

# 3. Cross-Site Scripting (XSS) Patterns
_XSS_PATTERNS = [
    re.compile(r"<\s*script\b[^>]*>", re.IGNORECASE),
    re.compile(r"javascript\s*:", re.IGNORECASE),
    re.compile(r"<\s*img\b[^>]+onerror\s*=", re.IGNORECASE),
    re.compile(r"<\s*iframe\b[^>]*>", re.IGNORECASE),
    re.compile(r"<\s*body\b[^>]+onload\s*=", re.IGNORECASE),
]

# 4. SQL Injection Patterns
_SQLI_PATTERNS = [
    re.compile(r"(\bUNION\b\s+\bSELECT\b)", re.IGNORECASE),
    re.compile(r"('\s*OR\s*'1'\s*=\s*'1)", re.IGNORECASE),
    re.compile(r"('\s*OR\s*1\s*=\s*1)", re.IGNORECASE),
    re.compile(r"(;\s*DROP\s+TABLE\b)", re.IGNORECASE),
    re.compile(r"(\bSELECT\s+\*\s+FROM\s+users\b)", re.IGNORECASE),
]

SAFE_REFUSAL_AR = (
    "⚠️ تم حظر هذا الاستفسار وفق معايير الأمان المعتمدة. "
    "المنظومة مخصصة حصرياً لتقديم الاستشارات الزراعية وتشخيص أمراض النباتات والري والتسميد، "
    "ولا تسمح بتمرير أوامر برمجية أو استعلامات مخالفة للغرض الزراعي."
)


def validate_prompt_safety(query: str) -> Tuple[bool, str, str]:
    """Scan an incoming prompt query for security risks.

    Returns:
        (is_safe, threat_category, response_message_ar)
    """
    if not query or not isinstance(query, str):
        return True, "none", ""

    text = query.strip()
    if not text:
        return True, "none", ""

    # 1. Check Prompt Injection / Jailbreaks
    for pat in _INJECTION_PATTERNS:
        if pat.search(text):
            return False, "prompt_injection", SAFE_REFUSAL_AR

    # 2. Check Code / OS Command Injection
    for pat in _CODE_INJECTION_PATTERNS:
        if pat.search(text):
            return False, "code_injection", SAFE_REFUSAL_AR

    # 3. Check XSS Payloads
    for pat in _XSS_PATTERNS:
        if pat.search(text):
            return False, "xss_injection", SAFE_REFUSAL_AR

    # 4. Check SQL Injection
    for pat in _SQLI_PATTERNS:
        if pat.search(text):
            return False, "sql_injection", SAFE_REFUSAL_AR

    return True, "none", ""
