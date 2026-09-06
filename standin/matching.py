"""Request matching.

The `Matcher` protocol is a single predicate, `matches(live, stored)`. Three
implementations ship:

* ``DefaultMatcher``: exact match on any subset of method/url/body, and
  JSON-body matching is key-order-insensitive.
* ``FuzzyMatcher``: method/url exact, but the body may differ up to a string
  similarity threshold, so a reworded or reformatted prompt still replays.
* ``SemanticMatcher``: method/url exact, but bodies match on embedding cosine
  similarity, so a paraphrase still replays. Dependency-free: you supply the
  ``embed`` callable (sentence-transformers, an API, whatever you like).

Any other strategy plugs in the same way: implement ``matches``.
"""
from __future__ import annotations

import difflib
import math
from collections.abc import Callable, Sequence
from typing import Protocol, runtime_checkable

from . import _codec
from .models import RawRequest, RecordedRequest
from .redaction import Redactor, redact_url_via

DEFAULT_MATCH_ON = ("method", "url", "body")
_SEP = ""


@runtime_checkable
class Matcher(Protocol):
    def matches(self, live: RawRequest, stored: RecordedRequest) -> bool: ...


@runtime_checkable
class KeyedMatcher(Protocol):
    """A matcher whose ``matches`` is exactly ``live_key(live) == stored_key(stored)``.

    Exposing the two key functions lets the cassette index interactions by key and
    look them up in O(1) instead of scanning. ``DefaultMatcher`` qualifies;
    ``FuzzyMatcher`` and ``SemanticMatcher`` deliberately do not (their match is a
    similarity test, not key equality), so they keep the linear scan.
    """

    def live_key(self, request: RawRequest) -> str: ...
    def stored_key(self, request: RecordedRequest) -> str: ...
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
            # Redact the URL on both sides identically, so a secret in the URL never
            # leaks into the match key and record/replay still line up after the
            # stored URL was redacted.
            parts.append(redact_url_via(self._redactor, request.url))
        if "body" in self._match_on:
            parts.append(_codec.canonical_live(request.body, _content_type(request.headers), self._redactor))
        return _SEP.join(parts)

    def stored_key(self, request: RecordedRequest) -> str:
        parts = []
        if "method" in self._match_on:
            parts.append(request.method.upper())
        if "url" in self._match_on:
            parts.append(redact_url_via(self._redactor, request.url))
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
        if "url" in self._match_on and redact_url_via(self._redactor, live.url) != redact_url_via(
            self._redactor, stored.url
        ):
            return False
        if "body" in self._match_on:
            lb = _codec.canonical_live(live.body, _content_type(live.headers), self._redactor)
            sb = _codec.canonical_stored(stored.body)
            if lb != sb and difflib.SequenceMatcher(None, lb, sb).ratio() < self.threshold:
                return False
        return True


class SemanticMatcher:
    """Match on meaning, not characters. method/url must match (per match_on); the
    body is embedded with the caller-supplied ``embed`` and accepted when the two
    vectors' cosine similarity is at least ``threshold``. Zero deps: wire ``embed``
    to sentence-transformers, an embeddings API, or any ``str -> Sequence[float]``."""

    def __init__(
        self,
        embed: Callable[[str], Sequence[float]],
        redactor: Redactor,
        match_on: Sequence[str] = DEFAULT_MATCH_ON,
        threshold: float = 0.95,
    ):
        self._embed = embed
        self._redactor = redactor
        self._match_on = tuple(match_on)
        self.threshold = threshold

    def matches(self, live: RawRequest, stored: RecordedRequest) -> bool:
        if "method" in self._match_on and live.method.upper() != stored.method.upper():
            return False
        if "url" in self._match_on and redact_url_via(self._redactor, live.url) != redact_url_via(
            self._redactor, stored.url
        ):
            return False
        if "body" in self._match_on:
            lb = _codec.canonical_live(live.body, _content_type(live.headers), self._redactor)
            sb = _codec.canonical_stored(stored.body)
            if lb != sb and _cosine(self._embed(lb), self._embed(sb)) < self.threshold:
                return False
        return True


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def _content_type(headers) -> str:
    for k, v in headers.items():
        if k.lower() == "content-type":
            return v
    return ""
