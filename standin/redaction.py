"""Redaction: keep credentials out of committed cassettes.

``Redactor`` is a Protocol so you can drop in your own policy; ``DefaultRedactor``
covers auth headers, secret field names, and common secret token formats, and
``NullRedactor`` is a no-op for when you explicitly want raw cassettes.

The header set, field-name set, and token patterns are module-level so the same
rules drive both scrubbing (``redact_*``) and the ``standin verify`` gate
(``scan_*``): one source of truth for what counts as a secret.
"""
from __future__ import annotations

import re
from collections.abc import Iterable
from re import Pattern
from typing import Any, Protocol, runtime_checkable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

PLACEHOLDER = "[REDACTED]"

SENSITIVE_HEADERS = frozenset({
    "authorization", "proxy-authorization", "x-api-key", "api-key",
    "openai-api-key", "anthropic-api-key", "x-goog-api-key",
    "cookie", "set-cookie",
})

# Body keys whose value is a secret regardless of its shape.
SECRET_FIELDS = frozenset({
    "api_key", "apikey", "access_token", "refresh_token", "id_token", "token",
    "session_token", "password", "secret", "client_secret", "private_key",
    "authorization",
})

# URL query-string / form-urlencoded keys whose value is a secret. Reuses the body
# field set (so custom field names extend URL redaction too) plus a few names that
# only ever appear in URLs (Google's ?key=, signed-URL ?sig=/?signature=).
_URL_ONLY_SECRET_KEYS = frozenset({"key", "token", "sig", "signature", "auth"})

SECRET_PATTERNS: list[Pattern[str]] = [
    re.compile(r"sk-ant-[A-Za-z0-9\-_]{20,}"),      # Anthropic
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9]{20,}"),   # OpenAI (incl. project keys)
    re.compile(r"AKIA[0-9A-Z]{16}"),                # AWS access key id
    re.compile(r"AIza[0-9A-Za-z\-_]{35}"),          # Google API key
    re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}"),      # GitHub token
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),    # Slack token
    # JSON Web Token: header.payload.signature, both header and payload base64url
    # of a JSON object (so they start with "eyJ" = '{"'). Very specific: JWTs are
    # bearer credentials and often show up in response bodies/headers.
    re.compile(r"eyJ[A-Za-z0-9_-]{6,}\.eyJ[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
]


def _snippet(value: Any, keep: int = 8) -> str:
    """A short, masked view of a secret: enough to locate, not to leak in CI logs."""
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
    def redact_url(self, url: str) -> str: ...


def redact_url_via(redactor: Any, url: str) -> str:
    """Redact ``url`` with ``redactor`` if it supports it, else return it unchanged.

    URL redaction was added after the original ``Redactor`` protocol, so this
    tolerates third-party redactors that predate ``redact_url``.
    """
    fn = getattr(redactor, "redact_url", None)
    return fn(url) if callable(fn) and isinstance(url, str) else url


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
        # A secret query/form key is any secret field name plus the URL-only ones.
        self._query_keys = self._fields | _URL_ONLY_SECRET_KEYS
        self._patterns = list(SECRET_PATTERNS) + [re.compile(p) for p in extra_patterns]

    # -- scrubbing -----------------------------------------------------------
    def redact_headers(self, headers: dict[str, str]) -> dict[str, str]:
        # Mask by name; for headers we don't know by name, still strip any
        # secret-shaped token from the value (so a token in X-Custom-Auth, a JWT,
        # etc. does not survive into the cassette).
        out: dict[str, str] = {}
        for k, v in headers.items():
            if k.lower() in self._headers:
                out[k] = PLACEHOLDER
            elif isinstance(v, str):
                out[k] = self.redact_text(v)
            else:
                out[k] = v
        return out

    def redact_text(self, text: str) -> str:
        for rx in self._patterns:
            text = rx.sub(PLACEHOLDER, text)
        return text

    # -- URL / query-string redaction ---------------------------------------
    def _redact_query(self, query: str) -> tuple[str, bool]:
        """Redact secret values in an ``a=b&c=d`` string. Returns (new, changed)."""
        if not query:
            return query, False
        pairs = parse_qsl(query, keep_blank_values=True)
        if not pairs:
            return query, False
        out: list[tuple[str, str]] = []
        changed = False
        for k, v in pairs:
            if k.lower() in self._query_keys and _looks_secret(v):
                out.append((k, PLACEHOLDER))
                changed = True
            else:
                nv = self.redact_text(v)
                changed = changed or nv != v
                out.append((k, nv))
        # keep the "[REDACTED]" marker literal (not %5BREDACTED%5D) for readability
        return (urlencode(out, safe="[]"), True) if changed else (query, False)

    def redact_query(self, text: str) -> str:
        """Redact a form-urlencoded body (same shape as a URL query string)."""
        if not isinstance(text, str) or not text:
            return text
        new, changed = self._redact_query(text)
        # If nothing keyed matched, still sweep for bare secret-shaped tokens.
        return new if changed else self.redact_text(text)

    def redact_url(self, url: str) -> str:
        """Strip credentials from a URL: userinfo, secret query values, and any
        secret-shaped token embedded anywhere in it."""
        if not isinstance(url, str) or not url:
            return url
        try:
            parts = urlsplit(url)
        except ValueError:
            return self.redact_text(url)
        changed = False
        netloc = parts.netloc
        if "@" in netloc:
            userinfo, _, host = netloc.rpartition("@")
            if userinfo and userinfo != PLACEHOLDER:
                netloc = f"{PLACEHOLDER}@{host}"
                changed = True
        new_query, q_changed = self._redact_query(parts.query)
        changed = changed or q_changed
        if changed:
            url = urlunsplit((parts.scheme, netloc, parts.path, new_query, parts.fragment))
        # Final sweep catches a secret shape in the path or elsewhere.
        return self.redact_text(url)

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
    def scan_url(self, url: Any) -> list[tuple[str, str]]:
        """Return (location, snippet) for a URL that still carries a live secret."""
        out: list[tuple[str, str]] = []
        if not isinstance(url, str) or not url:
            return out
        try:
            parts: Any = urlsplit(url)
        except ValueError:
            parts = None
        if parts is not None:
            if "@" in parts.netloc:
                userinfo = parts.netloc.rpartition("@")[0]
                if userinfo and userinfo != PLACEHOLDER:
                    out.append(("url userinfo", _snippet(userinfo)))
            for k, v in parse_qsl(parts.query, keep_blank_values=True):
                if k.lower() in self._query_keys and _looks_secret(v):
                    out.append((f"url query {k}", _snippet(v)))
        if not out:
            # Only fall back to a raw pattern sweep if nothing keyed was found, so
            # a query secret is reported once by name rather than twice.
            for rx in self._patterns:
                m = rx.search(url)
                if m is not None:
                    out.append(("url", _snippet(m.group(0))))
                    break
        return out

    def scan_query(self, text: Any) -> list[tuple[str, str]]:
        """Return (key, snippet) for a form-urlencoded body still carrying a secret."""
        out: list[tuple[str, str]] = []
        if not isinstance(text, str) or not text:
            return out
        for k, v in parse_qsl(text, keep_blank_values=True):
            if k.lower() in self._query_keys and _looks_secret(v):
                out.append((k, _snippet(v)))
        if not out:  # otherwise fall back to a bare token sweep over the whole body
            out.extend(self.scan_obj(text))
        return out

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

    def redact_url(self, url: str) -> str:
        return url

    def redact_query(self, text: str) -> str:
        return text
