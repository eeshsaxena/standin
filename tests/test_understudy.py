"""End-to-end tests using a local HTTP server (no real API keys needed).

Runnable either with pytest or directly: `python tests/test_understudy.py`.
"""
from __future__ import annotations

import http.server
import json
import socket
import threading
from pathlib import Path

import httpx

import understudy

_counter = {"n": 0}


class _Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):  # keep the test output quiet
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
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            body = json.dumps({
                "id": f"chatcmpl-{_counter['n']}",
                "choices": [{"message": {"role": "assistant", "content": f"reply #{_counter['n']}"}}],
            }).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)


def _start_server():
    port = _free_port()
    srv = http.server.HTTPServer(("127.0.0.1", port), _Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv, f"http://127.0.0.1:{port}"


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def test_record_then_replay_offline(tmp_path):
    cass = tmp_path / "chat.json"
    srv, base = _start_server()
    try:
        with understudy.use_cassette(cass, mode="all"):
            r = httpx.post(f"{base}/v1/chat", json={"model": "gpt", "messages": [{"role": "user", "content": "hi"}]})
        recorded = r.json()["choices"][0]["message"]["content"]
    finally:
        srv.shutdown()

    # Server is DOWN now. A real call would fail; replay must return the recording.
    with understudy.use_cassette(cass, mode="none"):
        r2 = httpx.post(f"{base}/v1/chat", json={"model": "gpt", "messages": [{"role": "user", "content": "hi"}]})
    assert r2.json()["choices"][0]["message"]["content"] == recorded
    assert cass.exists()


def test_streaming_record_replay(tmp_path):
    cass = tmp_path / "stream.json"
    srv, base = _start_server()
    payload = {"model": "gpt", "stream": True, "messages": [{"role": "user", "content": "hi"}]}
    try:
        with understudy.use_cassette(cass, mode="all"):
            with httpx.stream("POST", f"{base}/v1/stream", json=payload) as resp:
                live = "".join(resp.iter_text())
    finally:
        srv.shutdown()

    with understudy.use_cassette(cass, mode="none"):
        with httpx.stream("POST", f"{base}/v1/stream", json=payload) as resp:
            replayed = "".join(resp.iter_text())
    assert replayed == live
    assert "Hello" in replayed and "[DONE]" in replayed


def test_secrets_are_redacted(tmp_path):
    cass = tmp_path / "secret.json"
    srv, base = _start_server()
    leak = "sk-ant-abcdefghijklmnopqrstuvwxyz0123456789"
    try:
        with understudy.use_cassette(cass, mode="all"):
            httpx.post(
                f"{base}/v1/chat",
                headers={"Authorization": "Bearer sk-secretsecretsecretsecret1234"},
                json={"model": "gpt", "messages": [{"role": "user", "content": f"my key is {leak}"}]},
            )
    finally:
        srv.shutdown()
    text = cass.read_text(encoding="utf-8")
    assert leak not in text, "secret in body was not redacted"
    assert "sk-secretsecret" not in text, "Authorization header was not redacted"
    assert "[REDACTED]" in text


def test_replay_only_errors_on_unrecorded(tmp_path):
    cass = tmp_path / "empty.json"
    try:
        with understudy.use_cassette(cass, mode="none"):
            httpx.post("http://127.0.0.1:1/v1/chat", json={"x": 1})
        raised = False
    except understudy.CannotReplay:
        raised = True
    assert raised, "replay-only mode should refuse an unrecorded call"


if __name__ == "__main__":
    import tempfile

    passed = 0
    for fn in (test_record_then_replay_offline, test_streaming_record_replay,
               test_secrets_are_redacted, test_replay_only_errors_on_unrecorded):
        with tempfile.TemporaryDirectory() as d:
            fn(Path(d))
        print(f"  ok  {fn.__name__}")
        passed += 1
    print(f"\n{passed}/4 passed")
