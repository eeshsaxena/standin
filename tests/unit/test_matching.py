from standin.matching import DefaultMatcher
from standin.models import RawRequest, RecordedRequest
from standin.redaction import DefaultRedactor, NullRedactor


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


def test_url_redaction_keeps_live_and_stored_keys_aligned():
    # After the URL secret is redacted on disk, a live request with the raw URL must
    # still match: the matcher has to redact both sides identically.
    m = DefaultMatcher(DefaultRedactor(), match_on=("method", "url"))
    live = RawRequest("GET", "https://api/x?api_key=sk-proj-" + "A" * 24, {}, b"")
    stored = RecordedRequest("GET", "https://api/x?api_key=[REDACTED]", {}, {"empty": True})
    assert m.live_key(live) == m.stored_key(stored)


def test_old_raw_url_cassette_still_replays():
    # A pre-0.7.1 cassette stored the raw secret URL. Redacting both sides at match
    # time still lines the live request up with that old recording.
    m = DefaultMatcher(DefaultRedactor(), match_on=("method", "url"))
    secret_url = "https://api/x?api_key=sk-proj-" + "A" * 24
    live = RawRequest("GET", secret_url, {}, b"")
    stored = RecordedRequest("GET", secret_url, {}, {"empty": True})  # raw, as old code wrote it
    assert m.live_key(live) == m.stored_key(stored)


def test_url_secret_does_not_reach_the_match_key():
    m = DefaultMatcher(DefaultRedactor(), match_on=("method", "url"))
    live = RawRequest("GET", "https://api/x?api_key=sk-proj-" + "A" * 24, {}, b"")
    assert "sk-proj-" not in m.live_key(live)


def test_body_sniffed_as_json_without_content_type_header():
    # No content-type header at all: a JSON-looking body is still canonicalized as
    # JSON, so it matches the stored recording order-insensitively.
    m = DefaultMatcher(NullRedactor())
    live = RawRequest("POST", "http://x/v1", {}, b'{"b":2,"a":1}')
    stored = RecordedRequest("POST", "http://x/v1", {}, {"json": {"a": 1, "b": 2}})
    assert m.live_key(live) == m.stored_key(stored)
