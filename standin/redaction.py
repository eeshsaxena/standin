"""Redaction: keep credentials out of committed cassettes.

``Redactor`` is a Protocol so you can drop in your own policy; ``DefaultRedactor``
covers auth headers and common secret token formats, and ``NullRedactor`` is a
no-op for when you explicitly want raw cassettes.
"""
from __future__ import annotations

import re
from re import Pattern
from typing import Any, Protocol, runtime_checkable

PLACEHOLDER = "[REDACTED]"

SENSITIVE_HEADERS = frozenset({
    "authorization", "x-api-key", "api-key", "openai-api-key", "anthropic-api-key",
    "x-goog-api-key", "cookie", "set-cookie", "proxy-authorization",
})

SECRET_PATTERNS: list[Pattern] = [
    re.compile(r"sk-ant-[A-Za-z0-9\-_]{20,}"),
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"AIza[0-9A-Za-z\-_]{35}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
]


@runtime_checkable
class Redactor(Protocol):
    def redact_headers(self, headers: dict[str, str]) -> dict[str, str]: ...
    def redact_text(self, text: str) -> str: ...
    def redact_obj(self, obj: Any) -> Any: ...


class DefaultRedactor:
    """Masks sensitive headers and secret-looking tokens in bodies."""

    def __init__(self, extra_headers=(), extra_patterns=()):
        self._headers = SENSITIVE_HEADERS | {h.lower() for h in extra_headers}
        self._patterns = list(SECRET_PATTERNS) + [re.compile(p) for p in extra_patterns]

    def redact_headers(self, headers: dict[str, str]) -> dict[str, str]:
        return {k: (PLACEHOLDER if k.lower() in self._headers else v) for k, v in headers.items()}

    def redact_text(self, text: str) -> str:
        for rx in self._patterns:
            text = rx.sub(PLACEHOLDER, text)
        return text

    def redact_obj(self, obj: Any) -> Any:
        if isinstance(obj, str):
            return self.redact_text(obj)
        if isinstance(obj, dict):
            return {k: self.redact_obj(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self.redact_obj(v) for v in obj]
        return obj


class NullRedactor:
    """No-op redactor (used when redaction is turned off)."""

    def redact_headers(self, headers: dict[str, str]) -> dict[str, str]:
        return dict(headers)

    def redact_text(self, text: str) -> str:
        return text

    def redact_obj(self, obj: Any) -> Any:
        return obj
