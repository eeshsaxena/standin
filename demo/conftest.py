"""Demo harness: a local server that mimics the OpenAI API with realistic latency.

This lets the demo run with no API key while still showing the real win: the
first run pays the latency (as a live call would), the replay is instant.
"""
from __future__ import annotations

import http.server
import json
import threading
import time

import pytest

LATENCY_SECONDS = 1.5  # stand-in for real API latency (and cost)
FAKE_PORT = 8791  # fixed so the recorded URL is stable across runs (like a real API)


class _Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        self.rfile.read(n)
        time.sleep(LATENCY_SECONDS)
        body = json.dumps({
            "id": "chatcmpl-demo", "object": "chat.completion", "created": 0, "model": "gpt-4o-mini",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "A concise summary."}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 42, "completion_tokens": 8, "total_tokens": 50},
        }).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture(autouse=True)
def fake_openai(monkeypatch):
    srv = http.server.HTTPServer(("127.0.0.1", FAKE_PORT), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setenv("OPENAI_BASE_URL", f"http://127.0.0.1:{FAKE_PORT}/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-demo-not-a-real-key")
    try:
        yield
    finally:
        srv.shutdown()
        srv.server_close()
