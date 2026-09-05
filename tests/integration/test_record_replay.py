"""End-to-end record/replay against a local server (no API keys needed)."""
from __future__ import annotations

import httpx
import pytest

import standin


def test_record_then_replay_offline(tmp_path, llm_server):
    cass = tmp_path / "chat.json"
    payload = {"model": "gpt", "messages": [{"role": "user", "content": "hi"}]}
    with standin.use_cassette(cass, mode="all"):
        r = httpx.post(f"{llm_server.url}/v1/chat", json=payload)
    recorded = r.json()["choices"][0]["message"]["content"]

    llm_server.stop()  # a real call would now fail; replay must succeed
    with standin.use_cassette(cass, mode="none"):
        r2 = httpx.post(f"{llm_server.url}/v1/chat", json=payload)
    assert r2.json()["choices"][0]["message"]["content"] == recorded


def test_streaming_record_replay(tmp_path, llm_server):
    cass = tmp_path / "stream.json"
    payload = {"model": "gpt", "stream": True, "messages": [{"role": "user", "content": "hi"}]}
    with standin.use_cassette(cass, mode="all"):
        with httpx.stream("POST", f"{llm_server.url}/v1/stream", json=payload) as resp:
            live = "".join(resp.iter_text())

    llm_server.stop()
    with standin.use_cassette(cass, mode="none"):
        with httpx.stream("POST", f"{llm_server.url}/v1/stream", json=payload) as resp:
            replayed = "".join(resp.iter_text())
    assert replayed == live
    assert "Hello" in replayed and "[DONE]" in replayed


def test_secrets_redacted_in_cassette(tmp_path, llm_server):
    cass = tmp_path / "secret.json"
    leak = "sk-ant-abcdefghijklmnopqrstuvwxyz0123456789"
    with standin.use_cassette(cass, mode="all"):
        httpx.post(
            f"{llm_server.url}/v1/chat",
            headers={"Authorization": "Bearer sk-secretsecretsecretsecret1234"},
            json={"model": "gpt", "messages": [{"role": "user", "content": f"my key {leak}"}]},
        )
    text = cass.read_text(encoding="utf-8")
    assert leak not in text
    assert "sk-secretsecret" not in text
    assert "[REDACTED]" in text


def test_replay_only_errors_on_unrecorded(tmp_path):
    cass = tmp_path / "empty.json"
    with pytest.raises(standin.CannotReplay):
        with standin.use_cassette(cass, mode="none"):
            httpx.post("http://127.0.0.1:1/v1/chat", json={"x": 1})


def test_agent_loop_replays_in_order(tmp_path, llm_server):
    """Two identical requests must replay their two distinct recordings in order."""
    cass = tmp_path / "loop.json"
    payload = {"model": "gpt", "messages": [{"role": "user", "content": "same"}]}
    with standin.use_cassette(cass, mode="all"):
        a = httpx.post(f"{llm_server.url}/v1/chat", json=payload).json()["id"]
        b = httpx.post(f"{llm_server.url}/v1/chat", json=payload).json()["id"]
    assert a != b

    llm_server.stop()
    with standin.use_cassette(cass, mode="none"):
        a2 = httpx.post(f"{llm_server.url}/v1/chat", json=payload).json()["id"]
        b2 = httpx.post(f"{llm_server.url}/v1/chat", json=payload).json()["id"]
    assert (a2, b2) == (a, b)
