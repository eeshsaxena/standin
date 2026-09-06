"""A replay miss explains *why* nothing matched."""
from __future__ import annotations

import json

import pytest

from standin.cassette import Cassette
from standin.config import Config
from standin.engine import Engine
from standin.exceptions import CannotReplay
from standin.models import Interaction, Mode, RawRequest, RecordedRequest, RecordedResponse


def _interaction(body_json):
    return Interaction(
        request=RecordedRequest("POST", "http://api/x", {}, {"json": body_json}),
        response=RecordedResponse(200, {}, {"json": {"ok": True}}),
    )


def _engine(interactions):
    return Engine(Cassette(path="x", interactions=interactions), Config(mode=Mode.NONE))


def _raw(body: bytes, url="http://api/x", method="POST"):
    return RawRequest(method, url, {"content-type": "application/json"}, body)


def _fail(_request):  # do_real should never run in replay-only mode
    raise AssertionError("network was called")


def test_empty_cassette_says_so():
    with pytest.raises(CannotReplay) as exc:
        _engine([]).handle(_raw(b'{"a":1}'), _fail)
    assert "cassette is empty" in str(exc.value)


def test_already_replayed_is_diagnosed():
    engine = _engine([_interaction({"a": 1})])
    engine.handle(_raw(b'{"a":1}'), _fail)  # consume the only matching recording
    with pytest.raises(CannotReplay) as exc:
        engine.handle(_raw(b'{"a":1}'), _fail)
    assert "already replayed" in str(exc.value)


def test_closest_body_diff_is_shown():
    engine = _engine([_interaction({"model": "gpt", "prompt": "hello"})])
    with pytest.raises(CannotReplay) as exc:
        engine.handle(_raw(b'{"model":"gpt","prompt":"HELLO"}'), _fail)
    message = str(exc.value)
    assert "Closest of 1 recording" in message
    assert "body" in message
    assert "hello" in message and "HELLO" in message  # both sides of the diff appear


def test_url_mismatch_is_shown():
    engine = _engine([_interaction({"a": 1})])
    with pytest.raises(CannotReplay) as exc:
        engine.handle(_raw(b'{"a":1}', url="http://api/y"), _fail)
    message = str(exc.value)
    assert "url" in message
    assert "http://api/x" in message and "http://api/y" in message


def test_method_mismatch_is_shown():
    # Same url and body, different verb: the closest recording differs by method.
    engine = _engine([_interaction({"a": 1})])
    with pytest.raises(CannotReplay) as exc:
        engine.handle(_raw(b'{"a":1}', method="PUT"), _fail)
    message = str(exc.value)
    assert "method" in message
    assert "'PUT'" in message and "'POST'" in message


def test_text_body_diff_renders_line_by_line():
    # A non-JSON body diff: the pretty-printer can't json.loads it, so it falls
    # back to plain lines. The live request also carries no content-type header.
    recorded = Interaction(
        request=RecordedRequest("POST", "http://api/x", {}, {"text": "the quick brown fox"}),
        response=RecordedResponse(200, {}, {"json": {"ok": True}}),
    )
    engine = _engine([recorded])
    live = RawRequest("POST", "http://api/x", {}, b"the quick brown dog")
    with pytest.raises(CannotReplay) as exc:
        engine.handle(live, _fail)
    message = str(exc.value)
    assert "body" in message
    assert "fox" in message and "dog" in message


def test_huge_body_diff_is_truncated():
    recorded = _interaction({f"k{i}": i for i in range(60)})
    engine = _engine([recorded])
    live_body = json.dumps({f"k{i}": i + 1000 for i in range(60)}).encode()
    with pytest.raises(CannotReplay) as exc:
        engine.handle(_raw(live_body), _fail)
    assert "(diff truncated)" in str(exc.value)
