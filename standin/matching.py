"""Request matching.

``Matcher`` is a Protocol; ``DefaultMatcher`` matches on any subset of
method / url / body, is JSON-body-aware, and runs the same redaction over the
live body it does over the stored one so the two keys line up.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from . import _codec
from .models import RawRequest, RecordedRequest
from .redaction import Redactor

DEFAULT_MATCH_ON = ("method", "url", "body")
_SEP = ""


@runtime_checkable
class Matcher(Protocol):
    def live_key(self, request: RawRequest) -> str: ...
    def stored_key(self, request: RecordedRequest) -> str: ...


class DefaultMatcher:
    def __init__(self, redactor: Redactor, match_on: Sequence[str] = DEFAULT_MATCH_ON):
        self._redactor = redactor
        self._match_on = tuple(match_on)

    def live_key(self, request: RawRequest) -> str:
        parts = []
        if "method" in self._match_on:
            parts.append(request.method.upper())
        if "url" in self._match_on:
            parts.append(request.url)
        if "body" in self._match_on:
            ct = _content_type(request.headers)
            parts.append(_codec.canonical_live(request.body, ct, self._redactor))
        return _SEP.join(parts)

    def stored_key(self, request: RecordedRequest) -> str:
        parts = []
        if "method" in self._match_on:
            parts.append(request.method.upper())
        if "url" in self._match_on:
            parts.append(request.url)
        if "body" in self._match_on:
            parts.append(_codec.canonical_stored(request.body))
        return _SEP.join(parts)


def _content_type(headers) -> str:
    for k, v in headers.items():
        if k.lower() == "content-type":
            return v
    return ""
