"""Cassette storage: recorded (request, response) interactions as readable JSON."""
from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import redaction

VERSION = 1


def _encode_body(raw: bytes, content_type: str) -> dict:
    """Store a body as parsed JSON when possible (readable), else text, else base64."""
    if not raw:
        return {"empty": True}
    if "application/json" in content_type:
        try:
            return {"json": redaction.redact_obj(json.loads(raw.decode("utf-8")))}
        except (ValueError, UnicodeDecodeError):
            pass
    try:
        return {"text": redaction.redact_text(raw.decode("utf-8"))}
    except UnicodeDecodeError:
        return {"b64": base64.b64encode(raw).decode("ascii")}


def _decode_body(body: dict) -> bytes:
    if not body or body.get("empty"):
        return b""
    if "json" in body:
        return json.dumps(body["json"]).encode("utf-8")
    if "text" in body:
        return body["text"].encode("utf-8")
    if "b64" in body:
        return base64.b64decode(body["b64"])
    return b""


@dataclass
class Interaction:
    request: dict
    response: dict
    played: bool = False


@dataclass
class Cassette:
    path: Path
    interactions: list[Interaction] = field(default_factory=list)
    dirty: bool = False

    @classmethod
    def load(cls, path) -> "Cassette":
        path = Path(path)
        if not path.exists():
            return cls(path=path)
        data = json.loads(path.read_text(encoding="utf-8"))
        items = [Interaction(request=i["request"], response=i["response"]) for i in data.get("interactions", [])]
        return cls(path=path, interactions=items)

    def save(self) -> None:
        if not self.dirty:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": VERSION,
            "recorded_with": "understudy",
            "interactions": [{"request": i.request, "response": i.response} for i in self.interactions],
        }
        self.path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    # -- recording --
    def record(self, *, method: str, url: str, req_headers: dict, req_body: bytes,
               status_code: int, resp_headers: dict, resp_body: bytes) -> None:
        req_ct = req_headers.get("content-type", "") if req_headers else ""
        resp_ct = resp_headers.get("content-type", "")
        self.interactions.append(Interaction(
            request={
                "method": method.upper(),
                "url": url,
                "headers": redaction.redact_headers(dict(req_headers or {})),
                "body": _encode_body(req_body, req_ct),
            },
            response={
                "status_code": status_code,
                "headers": redaction.redact_headers(dict(resp_headers or {})),
                "body": _encode_body(resp_body, resp_ct),
            },
        ))
        self.dirty = True

    def response_bytes(self, interaction: Interaction) -> tuple[int, dict, bytes]:
        r = interaction.response
        return r["status_code"], dict(r.get("headers", {})), _decode_body(r.get("body", {}))
