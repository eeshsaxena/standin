from standin.matching import DefaultMatcher
from standin.models import RawRequest, RecordedRequest
from standin.redaction import NullRedactor


def test_json_key_order_does_not_matter():
    m = DefaultMatcher(NullRedactor())
    live = RawRequest("POST", "http://x/v1", {"content-type": "application/json"}, b'{"b":2,"a":1}')
    stored = RecordedRequest("POST", "http://x/v1", {}, {"json": {"a": 1, "b": 2}})
    assert m.live_key(live) == m.stored_key(stored)


def test_different_body_does_not_match():
    m = DefaultMatcher(NullRedactor())
    live = RawRequest("POST", "http://x/v1", {"content-type": "application/json"}, b'{"a":1}')
    stored = RecordedRequest("POST", "http://x/v1", {}, {"json": {"a": 2}})
    assert m.live_key(live) != m.stored_key(stored)


def test_match_on_subset_ignores_body():
    m = DefaultMatcher(NullRedactor(), match_on=("method", "url"))
    live = RawRequest("POST", "http://x/v1", {"content-type": "application/json"}, b'{"a":1}')
    stored = RecordedRequest("POST", "http://x/v1", {}, {"json": {"a": 999}})
    assert m.live_key(live) == m.stored_key(stored)


def test_method_case_insensitive():
    m = DefaultMatcher(NullRedactor(), match_on=("method",))
    live = RawRequest("post", "http://x", {}, b"")
    stored = RecordedRequest("POST", "http://x", {}, {"empty": True})
    assert m.live_key(live) == m.stored_key(stored)


def test_body_sniffed_as_json_without_content_type_header():
    # No content-type header at all: a JSON-looking body is still canonicalized as
    # JSON, so it matches the stored recording order-insensitively.
    m = DefaultMatcher(NullRedactor())
    live = RawRequest("POST", "http://x/v1", {}, b'{"b":2,"a":1}')
    stored = RecordedRequest("POST", "http://x/v1", {}, {"json": {"a": 1, "b": 2}})
    assert m.live_key(live) == m.stored_key(stored)
