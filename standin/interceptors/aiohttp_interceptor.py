"""aiohttp interceptor: routes ``aiohttp.ClientSession`` traffic through the engine.

Patches ``ClientSession._request`` once. On record, the real ``ClientResponse`` is
returned (its body pre-read and cached, so caller code can read it again). On replay,
a lightweight stand-in response is returned that implements the surface callers use:
``status``, ``headers``, ``read()``, ``text()``, ``json()``, ``raise_for_status()``
and the ``async with`` protocol. (aiohttp's real ClientResponse needs a live
connection to construct, so replay does not reconstruct it; streaming the response
body chunk-by-chunk is not supported on replay.) Inert with no cassette; a no-op if
aiohttp is not installed.
"""
from __future__ import annotations

import json as _json
import threading

from ..models import RawRequest, RawResponse
from .base import Interceptor, get_active_engine

_install_lock = threading.Lock()
_DROP = {"content-encoding", "content-length", "transfer-encoding"}


def _safe_headers(headers) -> dict[str, str]:
    return {k: v for k, v in headers.items() if k.lower() not in _DROP}


def _to_raw_request(method: str, str_or_url, kwargs) -> RawRequest:
    url = str(str_or_url)
    headers = {str(k): str(v) for k, v in dict(kwargs.get("headers") or {}).items()}
    if kwargs.get("json") is not None:
        body = _json.dumps(kwargs["json"]).encode("utf-8")
        headers.setdefault("Content-Type", "application/json")
    else:
        data = kwargs.get("data")
        if isinstance(data, (bytes, bytearray)):
            body = bytes(data)
        elif isinstance(data, str):
            body = data.encode("utf-8")
        else:
            body = b""  # FormData / stream uploads: best-effort, not canonicalized
    return RawRequest(method.upper(), url, headers, body)


class _ReplayResponse:
    """A minimal stand-in for aiohttp.ClientResponse, for replayed responses."""

    def __init__(self, raw: RawResponse, method: str, url: str):
        from multidict import CIMultiDict

        self.status = raw.status_code
        self._body = raw.body
        self.headers = CIMultiDict(_safe_headers(raw.headers))
        self.method = method.upper()
        self.url = url
        self.reason = ""

    def _encoding(self) -> str:
        ct = self.headers.get("content-type", "")
        if "charset=" in ct:
            return ct.split("charset=")[-1].split(";")[0].strip()
        return "utf-8"

    async def read(self) -> bytes:
        return self._body

    async def text(self, encoding: str | None = None) -> str:
        return self._body.decode(encoding or self._encoding())

    async def json(self, *, encoding: str | None = None, loads=_json.loads, content_type=None):
        return loads(self._body.decode(encoding or self._encoding()))

    def raise_for_status(self) -> None:
        if self.status >= 400:
            import aiohttp
            from yarl import URL

            info = aiohttp.RequestInfo(URL(self.url), self.method, self.headers, URL(self.url))  # type: ignore[arg-type]
            raise aiohttp.ClientResponseError(
                request_info=info, history=(), status=self.status, message=self.reason, headers=self.headers
            )

    def release(self) -> None:
        return None

    def close(self) -> None:
        return None

    async def __aenter__(self) -> _ReplayResponse:
        return self

    async def __aexit__(self, *exc) -> None:
        return None


class AiohttpInterceptor(Interceptor):
    _installed = False
    _orig = None

    def install(self) -> None:
        cls = AiohttpInterceptor
        if cls._installed:
            return
        with _install_lock:  # double-checked: patch aiohttp exactly once, thread-safely
            if cls._installed:
                return
            try:
                import aiohttp
            except ImportError:
                return  # aiohttp not installed; leave unpatched so a later install can retry
            self._patch(aiohttp)

    def _patch(self, aiohttp) -> None:
        cls = AiohttpInterceptor
        cls._orig = aiohttp.ClientSession._request
        orig = cls._orig

        async def patched_request(self, method, str_or_url, **kwargs):
            engine = get_active_engine()
            if engine is None:
                return await orig(self, method, str_or_url, **kwargs)

            captured: dict[str, object] = {}

            async def do_real(_raw):
                resp = await orig(self, method, str_or_url, **kwargs)
                body = await resp.read()  # caches resp._body so caller code can read it again
                captured["resp"] = resp
                return RawResponse(resp.status, dict(resp.headers), body)

            raw_resp = await engine.handle_async(_to_raw_request(method, str_or_url, kwargs), do_real)
            if "resp" in captured:  # record path: hand back the real, now-cached ClientResponse
                return captured["resp"]
            return _ReplayResponse(raw_resp, method, str(str_or_url))  # replay path

        aiohttp.ClientSession._request = patched_request  # type: ignore[method-assign]
        cls._installed = True
