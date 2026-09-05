"""httpx interceptor: routes all httpx traffic through the engine.

Patches ``httpx.HTTPTransport.handle_request`` and the async transport once.
Because OpenAI, Anthropic, Gemini, Mistral, Cohere, litellm, LangChain and
LlamaIndex all send over httpx, this single hook covers them.
"""
from __future__ import annotations

import httpx

from ..models import RawRequest, RawResponse
from .base import Interceptor, get_active_engine

# Headers to drop when rebuilding a response from already-decoded bytes, or httpx
# would try to decompress / re-length it a second time.
_DROP = {"content-encoding", "content-length", "transfer-encoding"}


def _safe_headers(headers):
    return [(k, v) for k, v in headers.items() if k.lower() not in _DROP]


def _to_httpx(raw: RawResponse, request) -> httpx.Response:
    return httpx.Response(
        status_code=raw.status_code,
        headers=_safe_headers(raw.headers),
        content=raw.body,
        request=request,
    )


def _to_raw_request(request) -> RawRequest:
    return RawRequest(request.method, str(request.url), dict(request.headers), request.content or b"")


class HttpxInterceptor(Interceptor):
    _installed = False
    _orig_sync = None
    _orig_async = None

    def install(self) -> None:
        cls = HttpxInterceptor
        if cls._installed:
            return
        cls._orig_sync = httpx.HTTPTransport.handle_request
        cls._orig_async = httpx.AsyncHTTPTransport.handle_async_request
        orig_sync = cls._orig_sync
        orig_async = cls._orig_async

        def patched_sync(self, request):
            engine = get_active_engine()
            if engine is None:
                return orig_sync(self, request)

            def do_real(_raw):
                resp = orig_sync(self, request)
                resp.read()
                return RawResponse(resp.status_code, dict(resp.headers), resp.content)

            raw_resp = engine.handle(_to_raw_request(request), do_real)
            return _to_httpx(raw_resp, request)

        async def patched_async(self, request):
            engine = get_active_engine()
            if engine is None:
                return await orig_async(self, request)

            async def do_real(_raw):
                resp = await orig_async(self, request)
                await resp.aread()
                return RawResponse(resp.status_code, dict(resp.headers), resp.content)

            raw_resp = await engine.handle_async(_to_raw_request(request), do_real)
            return _to_httpx(raw_resp, request)

        httpx.HTTPTransport.handle_request = patched_sync  # type: ignore[method-assign]
        httpx.AsyncHTTPTransport.handle_async_request = patched_async  # type: ignore[method-assign]
        cls._installed = True
