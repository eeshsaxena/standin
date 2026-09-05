"""Hook httpx's transport so every LLM SDK call is recorded or replayed.

We patch httpx.HTTPTransport.handle_request (and the async variant) once. The
patch is inert unless a cassette session is active, so importing understudy has
no effect until you open a cassette. Because OpenAI, Anthropic, Gemini, Mistral,
LangChain, LlamaIndex, litellm, etc. all send over httpx, one hook covers them.
"""
from __future__ import annotations

import httpx

from . import matchers

_active: "Session | None" = None
_installed = False
_orig_sync = None
_orig_async = None

# Headers we must drop when rebuilding a response from stored (already-decoded)
# bytes, or httpx would try to decompress/relength it a second time.
_DROP = {"content-encoding", "content-length", "transfer-encoding"}


class CannotReplay(Exception):
    """Raised in replay-only mode when no recorded interaction matches."""


def _safe_headers(headers: dict) -> list[tuple[str, str]]:
    return [(k, v) for k, v in headers.items() if k.lower() not in _DROP]


class Session:
    def __init__(self, cassette, mode: str, match_on: tuple):
        self.cassette = cassette
        self.mode = mode
        self.match_on = match_on
        self.preexisting = 0

    # -- policy --
    def _plan(self):
        try_replay = self.mode in ("none", "once", "new_episodes")
        record_on_miss = (
            self.mode in ("all", "new_episodes")
            or (self.mode == "once" and self.preexisting == 0)
        )
        return try_replay, record_on_miss

    def _find(self, key: str):
        for i in self.cassette.interactions:
            if not i.played and matchers.stored_key(i.request, self.match_on) == key:
                i.played = True
                return i
        return None

    def _replay(self, request, inter):
        status, headers, body = self.cassette.response_bytes(inter)
        return httpx.Response(status_code=status, headers=_safe_headers(headers),
                              content=body, request=request)

    def _rebuild(self, request, status, headers, body):
        return httpx.Response(status_code=status, headers=_safe_headers(dict(headers)),
                              content=body, request=request)

    def _key(self, request):
        return matchers.request_key(
            request.method, str(request.url), request.content or b"",
            request.headers.get("content-type", ""), self.match_on,
        )

    # -- sync --
    def handle(self, transport, request, original):
        try_replay, record_on_miss = self._plan()
        if try_replay:
            inter = self._find(self._key(request))
            if inter is not None:
                return self._replay(request, inter)
            if not record_on_miss:
                raise CannotReplay(f"understudy: no recorded call for {request.method} {request.url}")
        resp = original(transport, request)
        resp.read()
        body = resp.content
        self.cassette.record(
            method=request.method, url=str(request.url),
            req_headers=dict(request.headers), req_body=request.content or b"",
            status_code=resp.status_code, resp_headers=dict(resp.headers), resp_body=body,
        )
        return self._rebuild(request, resp.status_code, resp.headers, body)

    # -- async --
    async def handle_async(self, transport, request, original):
        try_replay, record_on_miss = self._plan()
        if try_replay:
            inter = self._find(self._key(request))
            if inter is not None:
                return self._replay(request, inter)
            if not record_on_miss:
                raise CannotReplay(f"understudy: no recorded call for {request.method} {request.url}")
        resp = await original(transport, request)
        await resp.aread()
        body = resp.content
        self.cassette.record(
            method=request.method, url=str(request.url),
            req_headers=dict(request.headers), req_body=request.content or b"",
            status_code=resp.status_code, resp_headers=dict(resp.headers), resp_body=body,
        )
        return self._rebuild(request, resp.status_code, resp.headers, body)


def install():
    global _installed, _orig_sync, _orig_async
    if _installed:
        return
    _orig_sync = httpx.HTTPTransport.handle_request
    _orig_async = httpx.AsyncHTTPTransport.handle_async_request

    def patched_sync(self, request):
        if _active is None:
            return _orig_sync(self, request)
        return _active.handle(self, request, _orig_sync)

    async def patched_async(self, request):
        if _active is None:
            return await _orig_async(self, request)
        return await _active.handle_async(self, request, _orig_async)

    httpx.HTTPTransport.handle_request = patched_sync
    httpx.AsyncHTTPTransport.handle_async_request = patched_async
    _installed = True


def set_active(session: "Session"):
    global _active
    prev, _active = _active, session
    return prev


def clear_active(prev):
    global _active
    _active = prev
