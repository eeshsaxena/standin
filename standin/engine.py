"""The record/replay policy engine.

The engine is deliberately transport-agnostic: it speaks only ``RawRequest`` /
``RawResponse`` and a ``do_real`` callback. Interceptors adapt a concrete client
(httpx, requests, aiohttp) to this interface, so all the decision logic lives
here in one testable place.
"""
from __future__ import annotations

import difflib
import json
from collections.abc import Awaitable
from typing import Callable

from . import _codec
from .cassette import Cassette
from .config import Config
from .exceptions import CannotReplay
from .matching import DefaultMatcher, KeyedMatcher
from .models import (
    Interaction,
    Mode,
    RawRequest,
    RawResponse,
    RecordedRequest,
    RecordedResponse,
)
from .redaction import DefaultRedactor

SyncReal = Callable[[RawRequest], RawResponse]
AsyncReal = Callable[[RawRequest], Awaitable[RawResponse]]


class Engine:
    def __init__(self, cassette: Cassette, config: Config):
        self.cassette = cassette
        self.config = config
        # Config.__post_init__ guarantees a redactor; narrow it for the type checker.
        self.redactor = config.redactor if config.redactor is not None else DefaultRedactor()
        self.matcher = config.matcher or DefaultMatcher(self.redactor, config.match_on)

    # -- policy -------------------------------------------------------------
    def _plan(self) -> tuple[bool, bool]:
        mode = self.config.mode
        try_replay = mode in (Mode.ONCE, Mode.NONE, Mode.NEW_EPISODES)
        record_on_miss = (
            mode in (Mode.ALL, Mode.NEW_EPISODES)
            or (mode is Mode.ONCE and self.cassette.preexisting == 0)
        )
        return try_replay, record_on_miss

    def _find(self, request: RawRequest):
        matcher = self.matcher
        # Key-based matchers (DefaultMatcher) get the O(1) index; matchers that only
        # implement `matches` (Fuzzy/Semantic/custom) keep the linear scan.
        if isinstance(matcher, KeyedMatcher):
            return self.cassette.find_unplayed_indexed(matcher.live_key, matcher.stored_key, request)
        return self.cassette.find_unplayed(matcher.matches, request)

    def _replay(self, interaction: Interaction) -> RawResponse:
        r = interaction.response
        return RawResponse(status_code=r.status_code, headers=dict(r.headers), body=_codec.decode_body(r.body))

    def _record(self, request: RawRequest, response: RawResponse) -> None:
        self.cassette.append(Interaction(
            request=RecordedRequest(
                method=request.method.upper(),
                url=request.url,
                headers=self.redactor.redact_headers(request.headers),
                body=_codec.encode_body(request.body, _ct(request.headers), self.redactor),
            ),
            response=RecordedResponse(
                status_code=response.status_code,
                headers=self.redactor.redact_headers(response.headers),
                body=_codec.encode_body(response.body, _ct(response.headers), self.redactor),
            ),
        ))

    def _miss(self, request: RawRequest) -> CannotReplay:
        """Build a replay-miss error that says *why* nothing matched.

        Three cases, most to least specific: an empty cassette; a request that does
        match a recording but whose recording was already replayed (the classic
        agent-loop / call-count mistake); or a genuine mismatch, in which case we
        show the closest recording and a field-level diff.
        """
        interactions = self.cassette.interactions
        head = f"standin: no recorded interaction matches {request.method} {request.url}"

        if not interactions:
            return CannotReplay(f"{head} (the cassette is empty). Record it first with mode 'once' or 'all'.")

        consumed = [i for i in interactions if self.matcher.matches(request, i.request)]
        if consumed:
            return CannotReplay(
                f"{head}: it matched {len(consumed)} recording(s), but they were all already replayed. "
                f"The code made more calls than were recorded, or in a different order. "
                f"Re-record with mode='all', or record the extra call with mode='new_episodes'."
            )

        live_body = _codec.canonical_live(request.body, _ct(request.headers), self.redactor)
        best = max(
            interactions,
            key=lambda i: difflib.SequenceMatcher(None, live_body, _codec.canonical_stored(i.request.body)).ratio(),
        )
        diffs = []
        if request.method.upper() != best.request.method.upper():
            diffs.append(f"  method: live={request.method.upper()!r} recorded={best.request.method.upper()!r}")
        if request.url != best.request.url:
            diffs.append(f"  url:\n    live:     {request.url}\n    recorded: {best.request.url}")
        stored_body = _codec.canonical_stored(best.request.body)
        if live_body != stored_body:
            ratio = difflib.SequenceMatcher(None, live_body, stored_body).ratio()
            diffs.append(f"  body ({ratio:.0%} similar):\n{_body_diff(stored_body, live_body)}")

        detail = "\n".join(diffs) or "  (closest recording differs only in a field you are not matching on)"
        return CannotReplay(
            f"{head}.\nClosest of {len(interactions)} recording(s) differs by:\n{detail}\n"
            f"Adjust the request to match, or re-record with mode='all'."
        )

    # -- entry points -------------------------------------------------------
    def handle(self, request: RawRequest, do_real: SyncReal) -> RawResponse:
        try_replay, record_on_miss = self._plan()
        if try_replay:
            inter = self._find(request)
            if inter is not None:
                return self._replay(inter)
            if not record_on_miss:
                raise self._miss(request)
        response = do_real(request)
        self._record(request, response)
        return response

    async def handle_async(self, request: RawRequest, do_real: AsyncReal) -> RawResponse:
        try_replay, record_on_miss = self._plan()
        if try_replay:
            inter = self._find(request)
            if inter is not None:
                return self._replay(inter)
            if not record_on_miss:
                raise self._miss(request)
        response = await do_real(request)
        self._record(request, response)
        return response


def _ct(headers) -> str:
    for k, v in headers.items():
        if k.lower() == "content-type":
            return v
    return ""


def _pretty(canonical: str) -> list[str]:
    """Pretty-print a canonical body so a diff reads line by line (JSON if it is JSON)."""
    try:
        return json.dumps(json.loads(canonical), indent=2, sort_keys=True, ensure_ascii=False).splitlines()
    except (ValueError, TypeError):
        return canonical.splitlines() or [canonical]


def _body_diff(recorded: str, live: str, max_lines: int = 40) -> str:
    diff = list(
        difflib.unified_diff(_pretty(recorded), _pretty(live), fromfile="recorded", tofile="live", lineterm="")
    )
    if len(diff) > max_lines:
        diff = diff[:max_lines] + ["... (diff truncated)"]
    return "\n".join("    " + line for line in diff)
