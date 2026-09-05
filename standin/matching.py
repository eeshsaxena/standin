"""Request matching.

The `Matcher` protocol is a single predicate, `matches(live, stored)`. Two
implementations ship:

* ``DefaultMatcher`` — exact match on any subset of method/url/body, and
  JSON-body matching is key-order-insensitive.
* ``FuzzyMatcher`` — method/url exact, but the body may differ up to a string
  similarity threshold, so a reworded or reformatted prompt still replays.

A true embedding/semantic matcher plugs in the same way: implement ``matches``.
"""
from __future__ import annotations

import difflib
from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from . import _codec
from .models import RawRequest, RecordedRequest
from .redaction import Redactor

DEFAULT_MATCH_ON = ("method", "url", "body")
_SEP = ""


@runtime_checkable
class Matcher(Protocol):
    def matches(self, live: RawRequest, stored: RecordedRequest) -> bool: ...


class DefaultMatcher:
    """Exact match on the chosen fields (JSON body compared order-insensitively)."""

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
            parts.append(_codec.canonical_live(request.body, _content_type(request.headers), self._redactor))
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

    def matches(self, live: RawRequest, stored: RecordedRequest) -> bool:
        return self.live_key(live) == self.stored_key(stored)


class FuzzyMatcher:
    """Tolerate small body drift. method/url must match (per match_on); the body
    must be at least ``threshold`` similar (difflib ratio, 0..1). Zero deps."""

    def __init__(self, redactor: Redactor, match_on: Sequence[str] = DEFAULT_MATCH_ON, threshold: float = 0.9):
        self._redactor = redactor
        self._match_on = tuple(match_on)
        self.threshold = threshold

    def matches(self, live: RawRequest, stored: RecordedRequest) -> bool:
        if "method" in self._match_on and live.method.upper() != stored.method.upper():
            return False
        if "url" in self._match_on and live.url != stored.url:
            return False
        if "body" in self._match_on:
            lb = _codec.canonical_live(live.body, _content_type(live.headers), self._redactor)
            sb = _codec.canonical_stored(stored.body)
            if lb != sb and difflib.SequenceMatcher(None, lb, sb).ratio() < self.threshold:
                return False
        return True


def _content_type(headers) -> str:
    for k, v in headers.items():
        if k.lower() == "content-type":
            return v
    return ""
