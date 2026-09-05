"""Strip secrets from cassettes so they are safe to commit to a public repo."""
from __future__ import annotations

import re

# Request headers that carry credentials and must never be written to a cassette.
SENSITIVE_HEADERS = {
    "authorization",
    "x-api-key",
    "api-key",
    "openai-api-key",
    "anthropic-api-key",
    "x-goog-api-key",
    "cookie",
    "set-cookie",
    "proxy-authorization",
}

# Secret value patterns to mask if they appear anywhere in a body.
SECRET_PATTERNS = [
    re.compile(r"sk-ant-[A-Za-z0-9\-_]{20,}"),
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"AIza[0-9A-Za-z\-_]{35}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
]

PLACEHOLDER = "[REDACTED]"


def redact_headers(headers: dict) -> dict:
    out = {}
    for k, v in headers.items():
        out[k] = PLACEHOLDER if k.lower() in SENSITIVE_HEADERS else v
    return out


def redact_text(text: str) -> str:
    for rx in SECRET_PATTERNS:
        text = rx.sub(PLACEHOLDER, text)
    return text


def redact_obj(obj):
    """Recursively mask secret-looking strings inside a JSON-like structure."""
    if isinstance(obj, str):
        return redact_text(obj)
    if isinstance(obj, dict):
        return {k: redact_obj(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact_obj(v) for v in obj]
    return obj
