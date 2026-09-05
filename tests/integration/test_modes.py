"""Every record/replay mode."""
from __future__ import annotations

import httpx
import pytest

import standin


def _id(url, content="hi"):
    r = httpx.post(f"{url}/v1/chat", json={"model": "g", "messages": [{"role": "user", "content": content}]})
    return r.json()["id"]


def test_once_records_then_replays(tmp_path, llm_server):
    cass = tmp_path / "c.json"
    with standin.use_cassette(cass, mode="once"):
        first = _id(llm_server.url)
    llm_server.stop()
    with standin.use_cassette(cass, mode="once"):
        again = _id(llm_server.url)
    assert again == first  # replayed, not a fresh call


def test_once_with_existing_is_replay_only(tmp_path, llm_server):
    cass = tmp_path / "c.json"
    with standin.use_cassette(cass, mode="all"):
        _id(llm_server.url, "recorded")
    llm_server.stop()
    with standin.use_cassette(cass, mode="once"):  # cassette exists -> replay-only
        with pytest.raises(standin.CannotReplay):
            _id(llm_server.url, "never recorded")


def test_all_always_records_fresh(tmp_path, llm_server):
    cass = tmp_path / "c.json"
    with standin.use_cassette(cass, mode="all"):
        a = _id(llm_server.url)
    with standin.use_cassette(cass, mode="all"):  # ignores existing, hits server again
        b = _id(llm_server.url)
    assert a != b


def test_new_episodes_replays_old_records_new(tmp_path, llm_server):
    cass = tmp_path / "c.json"
    with standin.use_cassette(cass, mode="all"):
        recorded_a = _id(llm_server.url, "A")
    with standin.use_cassette(cass, mode="new_episodes"):
        replayed_a = _id(llm_server.url, "A")   # replayed from cassette
        recorded_b = _id(llm_server.url, "B")   # new -> recorded live
    assert replayed_a == recorded_a
    assert recorded_b != recorded_a

    llm_server.stop()
    with standin.use_cassette(cass, mode="none"):
        assert _id(llm_server.url, "B") == recorded_b  # B is now on the cassette


def test_env_var_overrides_mode(tmp_path, llm_server, monkeypatch):
    cass = tmp_path / "c.json"
    with standin.use_cassette(cass, mode="all"):
        _id(llm_server.url)
    llm_server.stop()
    monkeypatch.setenv("STANDIN_MODE", "none")
    with standin.use_cassette(cass, mode="all"):  # env forces 'none'
        with pytest.raises(standin.CannotReplay):
            _id(llm_server.url, "unrecorded")


def test_invalid_mode_raises_configerror(tmp_path):
    with pytest.raises(standin.ConfigError):
        with standin.use_cassette(tmp_path / "c.json", mode="teleport"):
            pass

