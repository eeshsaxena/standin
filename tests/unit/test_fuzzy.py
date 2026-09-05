import json

from standin.matching import FuzzyMatcher
from standin.models import RawRequest, RecordedRequest
from standin.redaction import NullRedactor


def _live(body):
    return RawRequest("POST", "http://x/v1", {"content-type": "application/json"}, json.dumps(body).encode())


def _stored(body):
    return RecordedRequest("POST", "http://x/v1", {}, {"json": body})


def test_fuzzy_matches_near_identical_prompt():
    m = FuzzyMatcher(NullRedactor(), threshold=0.8)
    a = {"model": "gpt", "messages": [{"role": "user", "content": "Summarize the quarterly report please"}]}
    b = {"model": "gpt", "messages": [{"role": "user", "content": "Summarize the quarterly report, please."}]}
    assert m.matches(_live(a), _stored(b))


def test_fuzzy_rejects_very_different_prompt():
    m = FuzzyMatcher(NullRedactor(), threshold=0.9)
    a = {"model": "gpt", "messages": [{"role": "user", "content": "Summarize the quarterly report"}]}
    b = {"model": "gpt", "messages": [{"role": "user", "content": "Translate this haiku into French and explain the meter"}]}
    assert not m.matches(_live(a), _stored(b))


def test_fuzzy_url_must_still_match():
    m = FuzzyMatcher(NullRedactor())
    live = RawRequest("POST", "http://x/a", {"content-type": "application/json"}, b'{"k":1}')
    stored = RecordedRequest("POST", "http://x/b", {}, {"json": {"k": 1}})
    assert not m.matches(live, stored)


def test_fuzzy_identical_body_matches_at_any_threshold():
    m = FuzzyMatcher(NullRedactor(), threshold=1.0)
    body = {"model": "gpt", "messages": [{"role": "user", "content": "exact"}]}
    assert m.matches(_live(body), _stored(body))
