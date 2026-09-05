"""The real Anthropic SDK, pointed at the local server, recorded then replayed."""
from __future__ import annotations

import pytest

import standin

pytest.importorskip("anthropic")


def _client(url):
    from anthropic import Anthropic

    return Anthropic(base_url=url, api_key="sk-ant-SECRET-1234567890abcdefghij")


def test_anthropic_record_then_replay(tmp_path, llm_server):
    cass = tmp_path / "anthropic.json"
    with standin.use_cassette(cass, mode="all"):
        r = _client(llm_server.url).messages.create(
            model="claude-3-haiku-20240307", max_tokens=16,
            messages=[{"role": "user", "content": "hi"}],
        )
    recorded = r.content[0].text

    llm_server.stop()
    with standin.use_cassette(cass, mode="none"):
        r2 = _client(llm_server.url).messages.create(
            model="claude-3-haiku-20240307", max_tokens=16,
            messages=[{"role": "user", "content": "hi"}],
        )
    assert r2.content[0].text == recorded
    assert "sk-ant-SECRET" not in cass.read_text(encoding="utf-8")  # x-api-key redacted
