"""Error statuses, non-JSON bodies, multiple endpoints, redaction alignment."""
from __future__ import annotations

import httpx

import standin


def test_error_status_recorded_and_replayed(tmp_path, llm_server):
    cass = tmp_path / "err.json"
    with standin.use_cassette(cass, mode="all"):
        r = httpx.post(f"{llm_server.url}/v1/error", json={"x": 1})
    assert r.status_code == 429
    body = r.json()

    llm_server.stop()
    with standin.use_cassette(cass, mode="none"):
        r2 = httpx.post(f"{llm_server.url}/v1/error", json={"x": 1})
    assert r2.status_code == 429
    assert r2.json() == body


def test_non_json_bodies(tmp_path, llm_server):
    cass = tmp_path / "text.json"
    with standin.use_cassette(cass, mode="all"):
        r = httpx.post(f"{llm_server.url}/v1/text", content=b"raw prompt bytes",
                       headers={"content-type": "text/plain"})
    recorded = r.text
    assert recorded.startswith("plain reply")

    llm_server.stop()
    with standin.use_cassette(cass, mode="none"):
        r2 = httpx.post(f"{llm_server.url}/v1/text", content=b"raw prompt bytes",
                        headers={"content-type": "text/plain"})
    assert r2.text == recorded


def test_multiple_endpoints_matched_by_url(tmp_path, llm_server):
    cass = tmp_path / "multi.json"
    body = {"model": "g", "messages": [{"role": "user", "content": "hi"}]}
    with standin.use_cassette(cass, mode="all"):
        chat = httpx.post(f"{llm_server.url}/v1/chat", json=body).json()["id"]
        text = httpx.post(f"{llm_server.url}/v1/text", content=b"x", headers={"content-type": "text/plain"}).text

    llm_server.stop()
    with standin.use_cassette(cass, mode="none"):
        assert httpx.post(f"{llm_server.url}/v1/chat", json=body).json()["id"] == chat
        assert httpx.post(f"{llm_server.url}/v1/text", content=b"x", headers={"content-type": "text/plain"}).text == text


def test_content_type_preserved_on_replay(tmp_path, llm_server):
    cass = tmp_path / "ct.json"
    body = {"model": "g", "messages": [{"role": "user", "content": "hi"}]}
    with standin.use_cassette(cass, mode="all"):
        httpx.post(f"{llm_server.url}/v1/chat", json=body)
    llm_server.stop()
    with standin.use_cassette(cass, mode="none"):
        r = httpx.post(f"{llm_server.url}/v1/chat", json=body)
    assert "application/json" in r.headers["content-type"]


def test_secret_in_request_body_still_matches(tmp_path, llm_server):
    """A secret in the body is redacted in storage, but replay must still match
    (the matcher redacts the live body the same way)."""
    cass = tmp_path / "secretmatch.json"
    body = {"model": "g", "messages": [{"role": "user", "content": "token sk-ant-abcdefghijklmnopqrstuvwxyz0123"}]}
    with standin.use_cassette(cass, mode="all"):
        rec = httpx.post(f"{llm_server.url}/v1/chat", json=body).json()["id"]
    llm_server.stop()
    with standin.use_cassette(cass, mode="none"):
        assert httpx.post(f"{llm_server.url}/v1/chat", json=body).json()["id"] == rec
    assert "sk-ant-abcdef" not in cass.read_text(encoding="utf-8")


def test_inert_passthrough_without_cassette(tmp_path, llm_server):
    """With no cassette open, the httpx hook must be a transparent no-op."""
    with standin.use_cassette(tmp_path / "warm.json", mode="all"):
        pass  # ensure the patch is installed
    r = httpx.post(f"{llm_server.url}/v1/chat", json={"model": "g", "messages": []})
    assert r.status_code == 200  # normal live call, nothing recorded


def test_redact_false_keeps_raw(tmp_path, llm_server):
    cass = tmp_path / "raw.json"
    with standin.use_cassette(cass, mode="all", redact=False):
        httpx.post(f"{llm_server.url}/v1/chat", json={"model": "g", "messages": []},
                   headers={"authorization": "Bearer keepme-123"})
    assert "keepme-123" in cass.read_text(encoding="utf-8")
