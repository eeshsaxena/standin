"""Cassette persistence.

``CassetteStore`` is a Protocol so alternative formats (YAML, a single-file
archive, ...) can be added without touching the engine. ``JSONCassetteStore``
writes indented, reviewable JSON.
"""
from __future__ import annotations

import contextlib
import json
import os
import tempfile
from dataclasses import fields
from pathlib import Path
from typing import Protocol, runtime_checkable

from .exceptions import CassetteError
from .models import Interaction, RecordedRequest, RecordedResponse

FORMAT_VERSION = 1

_REQ_FIELDS = {f.name for f in fields(RecordedRequest)}
_RESP_FIELDS = {f.name for f in fields(RecordedResponse)}


@runtime_checkable
class CassetteStore(Protocol):
    def load(self, path: Path) -> list[Interaction]: ...
    def save(self, path: Path, interactions: list[Interaction]) -> None: ...


class JSONCassetteStore:
    def load(self, path: Path) -> list[Interaction]:
        path = Path(path)
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except ValueError as exc:
            raise CassetteError(f"cassette {path} is not valid JSON: {exc}") from exc
        except RecursionError as exc:
            # Pathologically nested JSON (a hostile cassette) must surface as a
            # clean CassetteError, not an uncaught RecursionError.
            raise CassetteError(f"cassette {path} is too deeply nested to parse") from exc
        version = data.get("version")
        if version != FORMAT_VERSION:
            raise CassetteError(f"cassette {path} has unsupported version {version!r}")
        out: list[Interaction] = []
        for idx, item in enumerate(data.get("interactions", [])):
            try:
                req = item["request"]
                resp = item["response"]
                # Ignore unknown keys so newer cassettes stay loadable (forward-compat).
                out.append(Interaction(
                    request=RecordedRequest(**{k: v for k, v in req.items() if k in _REQ_FIELDS}),
                    response=RecordedResponse(**{k: v for k, v in resp.items() if k in _RESP_FIELDS}),
                ))
            except (KeyError, TypeError, AttributeError) as exc:
                raise CassetteError(f"cassette {path} interaction {idx} is malformed: {exc}") from exc
        return out

    def save(self, path: Path, interactions: list[Interaction]) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": FORMAT_VERSION,
            "recorded_with": "standin",
            "interactions": [
                {
                    "request": vars(i.request),
                    "response": vars(i.response),
                }
                for i in interactions
            ],
        }
        text = json.dumps(data, indent=2, ensure_ascii=False)
        # Atomic write: never leave a half-written cassette if interrupted.
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(text)
            os.replace(tmp, path)
        except BaseException:
            with contextlib.suppress(OSError):
                os.unlink(tmp)
            raise
