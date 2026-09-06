"""Redaction: keep credentials out of committed cassettes.

``Redactor`` is a Protocol so you can drop in your own policy; ``DefaultRedactor``
covers auth headers, secret field names, and common secret token formats, and
``NullRedactor`` is a no-op for when you explicitly want raw cassettes.

The header set, field-name set, and token patterns are module-level so the same
rules drive both scrubbing (``redact_*``) and the ``standin verify`` gate
(``scan_*``) — one source of truth for what counts as a secret.
"""
from __future__ import annotations

import re
from collections.abc import Iterable
from re import Pattern
from typing import Any, Protocol, runtime_checkable

PLACEHOLDER = "[REDACTED]"

SENSITIVE_HEADERS = frozenset({
    "authorization", "proxy-authorization", "x-api-key", "api-key",
    "openai-api-key", "anthropic-api-key", "x-goog-api-key",
    "cookie", "set-cookie",
})

# Body keys whose value is a secret regardless of its shape.
SECRET_FIELDS = frozenset({
    "api_key", "apikey", "access_token", "refresh_token",
    "password", "secret", "client_secret", "authorization",
})

SECRET_PATTERNS: list[Pattern[str]] = [
    re.compile(r"sk-ant-[A-Za-z0-9\-_]{20,}"),      # Anthropic
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9]{20,}"),   # OpenAI (incl. project keys)
    re.compile(r"AKIA[0-9A-Z]{16}"),                # AWS access key id
    re.compile(r"AIza[0-9A-Za-z\-_]{35}"),          # Google API key
    re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}"),      # GitHub token
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),    # Slack token
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
]


def _snippet(value: Any, keep: int = 8) -> str:
    """A short, masked view of a secret — enough to locate, not to leak in CI logs."""
    text = str(value)
    return text if len(text) <= keep else text[:keep] + "..."


def _looks_secret(value: Any) -> bool:
    """A field value worth masking: a non-empty string that isn't already redacted."""
    return isinstance(value, str) and value != "" and value != PLACEHOLDER


@runtime_checkable
class Redactor(Protocol):
    def redact_headers(self, headers: dict[str, str]) -> dict[str, str]: ...
    def redact_text(self, text: str) -> str: ...
    def redact_obj(self, obj: Any) -> Any: ...


class DefaultRedactor:
    """Masks sensitive headers, secret field values, and secret-looking tokens."""

    def __init__(
        self,
        extra_headers: Iterable[str] = (),
        extra_patterns: Iterable[str] = (),
        extra_field_names: Iterable[str] = (),
    ):
        self._headers = SENSITIVE_HEADERS | {h.lower() for h in extra_headers}
        self._fields = SECRET_FIELDS | {f.lower() for f in extra_field_names}
        self._patterns = list(SECRET_PATTERNS) + [re.compile(p) for p in extra_patterns]

    # -- scrubbing -----------------------------------------------------------
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
            out: dict[Any, Any] = {}
            for k, v in obj.items():
                if isinstance(k, str) and k.lower() in self._fields and _looks_secret(v):
                    out[k] = PLACEHOLDER
                else:
                    out[k] = self.redact_obj(v)
            return out
        if isinstance(obj, list):
            return [self.redact_obj(v) for v in obj]
        return obj

    # -- scanning (used by ``standin verify``) -------------------------------
    def scan_headers(self, headers: Any) -> list[tuple[str, str]]:
        """Return (name, snippet) for headers that still carry a live secret."""
        out: list[tuple[str, str]] = []
        if not isinstance(headers, dict):
            return out
        for name, value in headers.items():
            if not isinstance(value, str):
                continue
            if name.lower() in self._headers:
                if _looks_secret(value):
                    out.append((name, _snippet(value)))
                continue
            for rx in self._patterns:
                m = rx.search(value)
                if m is not None:
                    out.append((name, _snippet(m.group(0))))
                    break
        return out

    def scan_obj(self, obj: Any, path: str = "") -> list[tuple[str, str]]:
        """Return (location, snippet) for values that still look like live secrets."""
        out: list[tuple[str, str]] = []
        if isinstance(obj, str):
            for rx in self._patterns:
                for m in rx.finditer(obj):
                    out.append((path or "value", _snippet(m.group(0))))
        elif isinstance(obj, dict):
            for k, v in obj.items():
                child = f"{path}.{k}" if path else str(k)
                if isinstance(k, str) and k.lower() in self._fields and _looks_secret(v):
                    out.append((child, _snippet(v)))
                else:
                    out.extend(self.scan_obj(v, child))
        elif isinstance(obj, list):
            for idx, v in enumerate(obj):
                out.extend(self.scan_obj(v, f"{path}[{idx}]"))
        return out


class NullRedactor:
    """No-op redactor (used when redaction is turned off)."""

    def redact_headers(self, headers: dict[str, str]) -> dict[str, str]:
        return dict(headers)

    def redact_text(self, text: str) -> str:
        return text

    def redact_obj(self, obj: Any) -> Any:
        return obj
