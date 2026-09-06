"""Shared fixtures: a local server that speaks OpenAI, Anthropic, and raw shapes.

No real API keys or network are ever used; the SDKs are pointed at this server.
"""
from __future__ import annotations

import http.server
import json
import socket
import threading

import pytest

pytest_plugins = ["pytester"]

_counter = {"n": 0}


def _openai_json(n):
    return {
        "id": f"chatcmpl-{n}", "object": "chat.completion", "created": 0, "model": "gpt-4o-mini",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": f"reply #{n}"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }


def _anthropic_json(n):
    return {
        "id": f"msg_{n}", "type": "message", "role": "assistant", "model": "claude-3-haiku-20240307",
        "content": [{"type": "text", "text": f"reply #{n}"}], "stop_reason": "end_turn", "stop_sequence": None,
        "usage": {"input_tokens": 1, "output_tokens": 1},
    }


def _openai_tool_json(n):
    return {
        "id": f"chatcmpl-{n}", "object": "chat.completion", "created": 0, "model": "gpt-4o-mini",
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant", "content": None,
                "tool_calls": [{
                    "id": f"call_{n}", "type": "function",
                    "function": {"name": "get_weather", "arguments": '{"city": "Paris"}'},
                }],
            },
            "finish_reason": "tool_calls",
        }],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }


def _openai_sse(n):
    base = {"id": f"chatcmpl-{n}", "object": "chat.completion.chunk", "created": 0, "model": "gpt-4o-mini"}
    chunks = [
        {**base, "choices": [{"index": 0, "delta": {"role": "assistant", "content": "Hello"}, "finish_reason": None}]},
        {**base, "choices": [{"index": 0, "delta": {"content": " world"}, "finish_reason": None}]},
        {**base, "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
    ]
    lines = [f"data: {json.dumps(c)}" for c in chunks] + ["data: [DONE]"]
    return ("\n\n".join(lines) + "\n\n").encode()


class _Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _read(self):
        n = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(n) if n else b""

    def _send(self, status, ctype, body):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        body = self._read()
        _counter["n"] += 1
        n = _counter["n"]
        path = self.path

        if path.endswith("/chat/completions"):
            if b'"tools"' in body:
                self._send(200, "application/json", json.dumps(_openai_tool_json(n)).encode())
            elif b'"stream": true' in body or b'"stream":true' in body:
                self._send(200, "text/event-stream", _openai_sse(n))
            else:
                self._send(200, "application/json", json.dumps(_openai_json(n)).encode())
        elif path.endswith("/messages"):
            self._send(200, "application/json", json.dumps(_anthropic_json(n)).encode())
        elif path == "/v1/stream":
            chunks = ['data: {"delta":"Hello"}', 'data: {"delta":" world"}', "data: [DONE]"]
            self._send(200, "text/event-stream", ("\n\n".join(chunks) + "\n\n").encode())
        elif path == "/v1/error":
            self._send(429, "application/json", json.dumps({"error": {"message": "rate limited", "n": n}}).encode())
        elif path == "/v1/text":
            self._send(200, "text/plain", f"plain reply #{n}".encode())
        elif path == "/v1/unicode":
            payload = json.dumps({"id": f"u{n}", "content": "café 日本語 🎬 mañana"}, ensure_ascii=False)
            self._send(200, "application/json", payload.encode("utf-8"))
        elif path == "/v1/big":
            payload = json.dumps({"id": f"big{n}", "content": "x" * 200_000})
            self._send(200, "application/json", payload.encode())
        else:
            self._send(200, "application/json", json.dumps({
                "id": f"chatcmpl-{n}",
                "choices": [{"message": {"role": "assistant", "content": f"reply #{n}"}}],
            }).encode())


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
