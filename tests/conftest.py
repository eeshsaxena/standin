"""Shared test fixtures: a tiny local 'LLM' HTTP server (JSON + SSE)."""
from __future__ import annotations

import http.server
import json
import socket
import threading

import pytest

_counter = {"n": 0}


class _Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):  # quiet
        pass

    def _read(self):
        n = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(n) if n else b""

    def do_POST(self):
        self._read()
        _counter["n"] += 1
        if self.path == "/v1/stream":
            chunks = [
                'data: {"choices":[{"delta":{"content":"Hello"}}]}',
                'data: {"choices":[{"delta":{"content":" world"}}]}',
                "data: [DONE]",
            ]
            body = ("\n\n".join(chunks) + "\n\n").encode()
            ctype = "text/event-stream"
        else:
            body = json.dumps({
                "id": f"chatcmpl-{_counter['n']}",
                "choices": [{"message": {"role": "assistant", "content": f"reply #{_counter['n']}"}}],
            }).encode()
            ctype = "application/json"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class _Server:
    def __init__(self, srv, url):
        self._srv = srv
        self.url = url
        self._stopped = False

    def stop(self):
        if not self._stopped:
            self._srv.shutdown()
            self._stopped = True


@pytest.fixture
def llm_server():
    port = _free_port()
    srv = http.server.HTTPServer(("127.0.0.1", port), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    server = _Server(srv, f"http://127.0.0.1:{port}")
    try:
        yield server
    finally:
        server.stop()
