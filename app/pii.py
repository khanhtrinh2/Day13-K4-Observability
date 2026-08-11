from __future__ import annotations

import hashlib
import re

PII_PATTERNS: dict[str, str] = {
    "email": r"[\w\.-]+@[\w\.-]+\.\w+",
    "phone_vn": r"(?<!\d)(?:\+84|0)(?:[ .-]?\d){9}(?!\d)",
    "cccd": r"\b\d{12}\b",
    "credit_card": r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b",
    "passport_vn": r"\b[A-Za-z]\d{7}\b",
    "address_vn": r"\b(?:số\s*)?\d{1,4}[A-Za-z]?(?:[\/\-]\d+)?\s+(?:đường|Đường|phố|Phố|ngõ|Ngõ|hẻm|Hẻm)\s+[^\d,\.\n]{1,40}"
    r"|\b(?:phường|Phường|quận|Quận|huyện|Huyện|tỉnh|Tỉnh)\s+[^\s,\.\n]{1,30}",
}


def scrub_text(text: str) -> str:
    safe = text
    for name, pattern in PII_PATTERNS.items():
        safe = re.sub(pattern, f"[REDACTED_{name.upper()}]", safe)
    return safe


def summarize_text(text: str, max_len: int = 80) -> str:
    safe = scrub_text(text).strip().replace("\n", " ")
    return safe[:max_len] + ("..." if len(safe) > max_len else "")


def hash_user_id(user_id: str) -> str:
    return hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:12]
