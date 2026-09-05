"""Hardening: atomic writes, tolerant loading, config validation."""
from __future__ import annotations

import json

import pytest

import standin
from standin.config import Config
from standin.exceptions import CassetteError, ConfigError
from standin.matching import DefaultMatcher
from standin.models import Interaction, RecordedRequest, RecordedResponse
from standin.redaction import NullRedactor
from standin.storage import JSONCassetteStore


def _interaction():
    return Interaction(
        request=RecordedRequest("POST", "http://x", {}, {"json": {"a": 1}}),
        response=RecordedResponse(200, {}, {"json": {"ok": True}}),
    )


def test_save_is_atomic_no_tmp_left(tmp_path):
    path = tmp_path / "c.json"
    JSONCassetteStore().save(path, [_interaction()])
    leftovers = [p.name for p in tmp_path.iterdir() if p.name != "c.json"]
    assert leftovers == []  # no *.tmp files remain
    json.loads(path.read_text(encoding="utf-8"))  # valid JSON


def test_loader_ignores_unknown_keys(tmp_path):
    path = tmp_path / "c.json"
    path.write_text(json.dumps({
        "version": 1,
        "interactions": [{
            "request": {"method": "POST", "url": "http://x", "headers": {}, "body": {}, "future_field": 1},
            "response": {"status_code": 200, "headers": {}, "body": {}, "latency_ms": 5},
        }],
    }), encoding="utf-8")
    loaded = JSONCassetteStore().load(path)
    assert len(loaded) == 1 and loaded[0].request.method == "POST"


def test_loader_rejects_malformed_interaction(tmp_path):
    path = tmp_path / "c.json"
    path.write_text(json.dumps({
        "version": 1,
        "interactions": [{"request": {"method": "POST", "url": "http://x"}}],  # no "response"
    }), encoding="utf-8")
    with pytest.raises(CassetteError):
        JSONCassetteStore().load(path)


def test_invalid_match_on_rejected():
    with pytest.raises(ConfigError):
        Config(match_on=("method", "headers"))  # 'headers' is not supported


def test_custom_matcher_bypasses_match_on_validation():
    # A user-supplied matcher may use any vocabulary, so match_on isn't validated.
    cfg = Config(matcher=DefaultMatcher(NullRedactor()), match_on=("anything",))
    assert cfg.matcher is not None


def test_use_cassette_invalid_match_on(tmp_path):
    with pytest.raises(standin.ConfigError):
        with standin.use_cassette(tmp_path / "c.json", match_on=("bogus",)):
            pass


def test_save_failure_cleans_up_tmp(tmp_path, monkeypatch):
    import os as _os

    path = tmp_path / "c.json"

    def boom(src, dst):
        raise OSError("simulated disk error")

    monkeypatch.setattr(_os, "replace", boom)
    with pytest.raises(OSError):
        JSONCassetteStore().save(path, [_interaction()])
    assert not path.exists()
    assert list(tmp_path.iterdir()) == []  # temp file cleaned up, nothing left behind

