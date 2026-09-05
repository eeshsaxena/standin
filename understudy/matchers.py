"""Decide whether a live request matches a recorded one. Body-aware for LLM JSON."""
from __future__ import annotations

import json

from . import redaction

DEFAULT_MATCH_ON = ("method", "url", "body")
_SEP = ""


def _live_body_canon(raw: bytes, content_type: str) -> str:
    if not raw:
        return ""
    if "application/json" in (content_type or ""):
        try:
            obj = json.loads(raw.decode("utf-8"))
            return json.dumps(redaction.redact_obj(obj), sort_keys=True, ensure_ascii=False)
        except (ValueError, UnicodeDecodeError):
            pass
    try:
        return redaction.redact_text(raw.decode("utf-8"))
    except UnicodeDecodeError:
        return ""


def _stored_body_canon(body: dict) -> str:
    if not body or body.get("empty"):
        return ""
    if "json" in body:
        return json.dumps(body["json"], sort_keys=True, ensure_ascii=False)
    if "text" in body:
        return body["text"]
    return ""


def request_key(method: str, url: str, body: bytes, content_type: str, match_on) -> str:
    parts = []
    if "method" in match_on:
        parts.append(method.upper())
    if "url" in match_on:
        parts.append(url)
    if "body" in match_on:
        parts.append(_live_body_canon(body, content_type))
    return _SEP.join(parts)


def stored_key(request: dict, match_on) -> str:
    parts = []
    if "method" in match_on:
        parts.append(str(request.get("method", "")).upper())
    if "url" in match_on:
        parts.append(str(request.get("url", "")))
    if "body" in match_on:
        parts.append(_stored_body_canon(request.get("body", {})))
    return _SEP.join(parts)
