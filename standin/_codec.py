"""Body (de)serialization and canonicalization.

A body is stored as one of ``{"json": ...}``, ``{"text": ...}``, ``{"b64": ...}``
or ``{"empty": true}`` so cassettes stay human-readable when possible. Canonical
forms are used only for request matching, never written to disk.
"""
from __future__ import annotations

import base64
import json
from typing import Any


def _try_json(raw: bytes, content_type: str) -> Any | None:
    if "application/json" not in (content_type or ""):
        # Some providers omit the header; still try if it smells like JSON.
        stripped = raw[:1]
        if stripped not in (b"{", b"["):
            return None
    try:
        return json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None


def encode_body(raw: bytes, content_type: str, redactor=None) -> dict[str, Any]:
    if not raw:
        return {"empty": True}
    obj = _try_json(raw, content_type)
    if obj is not None:
        if redactor is not None:
            obj = redactor.redact_obj(obj)
        return {"json": obj}
    try:
        text = raw.decode("utf-8")
        if redactor is not None:
            text = redactor.redact_text(text)
        return {"text": text}
    except UnicodeDecodeError:
        return {"b64": base64.b64encode(raw).decode("ascii")}


def decode_body(body: dict[str, Any]) -> bytes:
    if not body or body.get("empty"):
        return b""
    if "json" in body:
        return json.dumps(body["json"], ensure_ascii=False).encode("utf-8")
    if "text" in body:
        return body["text"].encode("utf-8")
    if "b64" in body:
        return base64.b64decode(body["b64"])
    return b""


def canonical_live(raw: bytes, content_type: str, redactor=None) -> str:
    """Canonical string for a live (in-flight) request body, for matching."""
    if not raw:
        return ""
    obj = _try_json(raw, content_type)
    if obj is not None:
        if redactor is not None:
            obj = redactor.redact_obj(obj)
        return json.dumps(obj, sort_keys=True, ensure_ascii=False)
    try:
        text = raw.decode("utf-8")
        return redactor.redact_text(text) if redactor is not None else text
    except UnicodeDecodeError:
        return base64.b64encode(raw).decode("ascii")


def canonical_stored(body: dict[str, Any]) -> str:
    """Canonical string for a stored request body, for matching."""
    if not body or body.get("empty"):
        return ""
    if "json" in body:
        return json.dumps(body["json"], sort_keys=True, ensure_ascii=False)
    if "text" in body:
        return body["text"]
    if "b64" in body:
        return body["b64"]
    return ""
