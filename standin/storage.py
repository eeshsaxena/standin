"""Cassette persistence.

``CassetteStore`` is a Protocol so alternative formats (YAML, a single-file
archive, ...) can be added without touching the engine. ``JSONCassetteStore``
writes indented, reviewable JSON.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol, runtime_checkable

from .exceptions import CassetteError
from .models import Interaction, RecordedRequest, RecordedResponse

FORMAT_VERSION = 1


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
        version = data.get("version")
        if version != FORMAT_VERSION:
            raise CassetteError(f"cassette {path} has unsupported version {version!r}")
        out: list[Interaction] = []
        for item in data.get("interactions", []):
            out.append(Interaction(
                request=RecordedRequest(**item["request"]),
                response=RecordedResponse(**item["response"]),
            ))
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
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
