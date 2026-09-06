"""A replay miss explains *why* nothing matched."""
from __future__ import annotations

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
