"""The real OpenAI SDK, pointed at the local server, recorded then replayed."""
from __future__ import annotations

import pytest

import standin

pytest.importorskip("openai")


def _client(url):
    from openai import OpenAI

    return OpenAI(base_url=f"{url}/v1", api_key="sk-test-SECRET-key-1234567890")


def test_openai_record_then_replay(tmp_path, llm_server):
    cass = tmp_path / "openai.json"
    with standin.use_cassette(cass, mode="all"):
        r = _client(llm_server.url).chat.completions.create(
            model="gpt-4o-mini", messages=[{"role": "user", "content": "hi"}]
        )
    recorded = r.choices[0].message.content

    llm_server.stop()
    with standin.use_cassette(cass, mode="none"):
        r2 = _client(llm_server.url).chat.completions.create(
            model="gpt-4o-mini", messages=[{"role": "user", "content": "hi"}]
        )
    assert r2.choices[0].message.content == recorded
    assert "sk-test-SECRET" not in cass.read_text(encoding="utf-8")  # auth header redacted


def test_openai_streaming(tmp_path, llm_server):
    cass = tmp_path / "openai_stream.json"

    def run(url):
        stream = _client(url).chat.completions.create(
            model="gpt-4o-mini", messages=[{"role": "user", "content": "hi"}], stream=True
        )
        return "".join(c.choices[0].delta.content or "" for c in stream if c.choices)

    with standin.use_cassette(cass, mode="all"):
        live = run(llm_server.url)
    llm_server.stop()
    with standin.use_cassette(cass, mode="none"):
        replayed = run(llm_server.url)
    assert replayed == live == "Hello world"
