"""requests interceptor: routes ``requests`` traffic through the engine.

Patches ``requests.adapters.HTTPAdapter.send`` once. Any SDK built on ``requests``
(rather than httpx) is covered by this single hook. Inert when no cassette is open,
and a no-op if ``requests`` is not installed.
"""
from __future__ import annotations

import io
import threading

from ..models import RawRequest, RawResponse
from .base import Interceptor, get_active_engine

_install_lock = threading.Lock()

# Bodies are stored/replayed already-decoded, so drop framing/encoding headers that
# would otherwise make the client try to decompress or re-length them a second time.
_DROP = {"content-encoding", "content-length", "transfer-encoding"}


def _safe_headers(headers) -> dict[str, str]:
    return {k: v for k, v in headers.items() if k.lower() not in _DROP}


def _to_raw_request(prepared) -> RawRequest:
    body = prepared.body
    if body is None:
        raw = b""
    elif isinstance(body, str):
        raw = body.encode("utf-8")
    elif isinstance(body, (bytes, bytearray)):
        raw = bytes(body)
    else:
        raw = b""  # streamed / file-like uploads can't be canonicalized; treat as empty
    return RawRequest(prepared.method or "GET", prepared.url or "", dict(prepared.headers), raw)


def _to_requests(raw: RawResponse, prepared):
    import requests
    from requests.structures import CaseInsensitiveDict

    resp = requests.Response()
    resp.status_code = raw.status_code
    resp.headers = CaseInsensitiveDict(_safe_headers(raw.headers))
    resp._content = raw.body
    resp._content_consumed = True
    resp.url = prepared.url
    resp.request = prepared
    resp.reason = requests.status_codes._codes.get(raw.status_code, ["", ""])[0].upper()
    resp.encoding = requests.utils.get_encoding_from_headers(resp.headers)
    resp.raw = io.BytesIO(raw.body)  # present for code that pokes at .raw; .content uses _content
    return resp


class RequestsInterceptor(Interceptor):
    _installed = False
    _orig = None

    def install(self) -> None:
        cls = RequestsInterceptor
        if cls._installed:
            return
        with _install_lock:  # double-checked: patch requests exactly once, thread-safely
            if cls._installed:
                return
            try:
                import requests.adapters as adapters
            except ImportError:
                return  # requests not installed; leave unpatched so a later install can retry
            self._patch(adapters)

    def _patch(self, adapters) -> None:
        cls = RequestsInterceptor
        cls._orig = adapters.HTTPAdapter.send
        orig = cls._orig

        def patched_send(self, request, **kwargs):
            engine = get_active_engine()
            if engine is None:
                return orig(self, request, **kwargs)

            def do_real(_raw):
                resp = orig(self, request, **kwargs)
                _ = resp.content  # force the body to be read while the connection is open
                return RawResponse(resp.status_code, dict(resp.headers), resp.content)

            raw_resp = engine.handle(_to_raw_request(request), do_real)
            return _to_requests(raw_resp, request)

        adapters.HTTPAdapter.send = patched_send  # type: ignore[method-assign]
        cls._installed = True
