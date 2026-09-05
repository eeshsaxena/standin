"""The record/replay policy engine.

The engine is deliberately transport-agnostic: it speaks only ``RawRequest`` /
``RawResponse`` and a ``do_real`` callback. Interceptors adapt a concrete client
(httpx today, others later) to this interface, so all the decision logic lives
here in one testable place.
"""
from __future__ import annotations

from collections.abc import Awaitable
from typing import Callable

from . import _codec
from .cassette import Cassette
from .config import Config
from .exceptions import CannotReplay
from .matching import DefaultMatcher
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
        return self.cassette.find_unplayed(self.matcher.stored_key, self.matcher.live_key(request))

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
        return CannotReplay(f"standin: no recorded interaction for {request.method} {request.url}")

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
