"""Live demo: record real LLM calls once, then replay them instantly and offline.

    python demo/demo.py

Self-contained: it starts a local stand-in for the OpenAI API (with realistic
latency) so it runs with no key and no network, yet shows the real win.
"""
from __future__ import annotations

import http.server
import json
import os
import shutil
import threading
import time
from pathlib import Path

import standin

PORT = 8792
LATENCY = 1.5  # seconds per call, mimicking a real model
CACHE = Path("demo/.cache/demo.json")
PROMPTS = [
    "Summarize the French Revolution in one line.",
    "Explain the CAP theorem simply.",
    "Write a haiku about unit tests.",
    "Name three sorting algorithms.",
    "What is a monad, briefly?",
]


class _Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        time.sleep(LATENCY)
        body = json.dumps({
            "id": "chatcmpl-demo", "object": "chat.completion", "created": 0, "model": "gpt-4o-mini",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "..."}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 40, "completion_tokens": 10, "total_tokens": 50},
        }).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _serve():
    srv = http.server.HTTPServer(("127.0.0.1", PORT), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def _run(mode: str) -> float:
    from openai import OpenAI

    client = OpenAI()
    start = time.perf_counter()
    with standin.use_cassette(CACHE, mode=mode):
        for prompt in PROMPTS:
            client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": prompt}])
    return time.perf_counter() - start


def main() -> None:
    os.environ["OPENAI_BASE_URL"] = f"http://127.0.0.1:{PORT}/v1"
    os.environ["OPENAI_API_KEY"] = "sk-demo-not-real"
    if CACHE.parent.exists():
        shutil.rmtree(CACHE.parent)

    srv = _serve()
    try:
        print(f"Calling a model {len(PROMPTS)} times inside a test...\n")
        recorded = _run("all")
        print(f"  1st run   real API calls, recording   {recorded:6.2f}s   $$$")
        replayed = _run("none")
        print(f"  every run replayed from cassette       {replayed:6.3f}s   $0.00  offline")
        print(f"\n  => {recorded / replayed:.0f}x faster, deterministic, no network, no keys.")
    finally:
        srv.shutdown()
        srv.server_close()


if __name__ == "__main__":
    main()
