"""Sensitive-data redaction utilities for prompts and audit-safe content capture."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class RedactionResult:
    text: str
    counts: dict[str, int]


_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("openai_key", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b")),
    ("password_kv", re.compile(r"(?i)\b(password|passwd|pwd)\s*[:=]\s*([^\s,;]{6,})")),
    ("bearer_token", re.compile(r"(?i)\bBearer\s+([A-Za-z0-9._-]{20,})")),
)

_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_PHONE = re.compile(r"\b(?:\+?1[-.\s]?)?(?:\(\d{3}\)|\d{3})[-.\s]?\d{3}[-.\s]?\d{4}\b")


def redact_text(text: str, *, redact_emails_phones: bool) -> RedactionResult:
    counts: dict[str, int] = {}

    def _bump(name: str, n: int) -> None:
        if n > 0:
            counts[name] = counts.get(name, 0) + n

    out = text
    for name, pat in _PATTERNS:
        out, n = pat.subn(lambda m, kind=name: _replacement(kind, m.group(0)), out)
        _bump(name, n)

    if redact_emails_phones:
        out, n = _EMAIL.subn("[REDACTED:email]", out)
        _bump("email", n)
        out, n = _PHONE.subn("[REDACTED:phone]", out)
        _bump("phone", n)

    return RedactionResult(text=out, counts=counts)


def _replacement(kind: str, raw: str) -> str:
    _ = raw
    return f"[REDACTED:{kind}]"
