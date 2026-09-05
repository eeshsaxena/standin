"""Property-based fuzzing of the pure functions (codec, redaction, matching)."""
from __future__ import annotations

import json

import pytest

pytest.importorskip("hypothesis")
from hypothesis import given  # noqa: E402
from hypothesis import strategies as st  # noqa: E402

from standin import _codec
from standin.matching import DefaultMatcher
from standin.models import RawRequest, RecordedRequest
from standin.redaction import DefaultRedactor, NullRedactor

# JSON values hypothesis can build (no NaN/inf, which JSON can't round-trip).
json_scalars = st.none() | st.booleans() | st.integers() | st.text() | st.floats(allow_nan=False, allow_infinity=False)
json_values = st.recursive(
    json_scalars,
    lambda c: st.lists(c, max_size=4) | st.dictionaries(st.text(max_size=8), c, max_size=4),
    max_leaves=15,
)


@given(st.binary().filter(lambda b: b[:1] not in (b"{", b"[")))
def test_codec_binary_roundtrip(raw):
    """Non-JSON bodies must survive encode -> decode byte-for-byte."""
    enc = _codec.encode_body(raw, "application/octet-stream")
    assert _codec.decode_body(enc) == raw


@given(json_values)
def test_codec_json_semantic_roundtrip(value):
    raw = json.dumps(value).encode("utf-8")
    enc = _codec.encode_body(raw, "application/json")
    assert json.loads(_codec.decode_body(enc)) == value


@given(st.text())
def test_redaction_is_idempotent(text):
    r = DefaultRedactor()
    once = r.redact_text(text)
    assert r.redact_text(once) == once


@given(st.dictionaries(st.text(min_size=1, max_size=10), json_scalars, max_size=6))
def test_matcher_key_is_order_independent(d):
    """Live and stored keys agree regardless of JSON key ordering."""
    m = DefaultMatcher(NullRedactor())
    raw = RawRequest("POST", "http://x/v1", {"content-type": "application/json"}, json.dumps(d).encode("utf-8"))
    stored = RecordedRequest("POST", "http://x/v1", {}, {"json": d})
    assert m.live_key(raw) == m.stored_key(stored)
