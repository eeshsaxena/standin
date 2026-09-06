import json
import re

from standin.matching import SemanticMatcher
from standin.models import RawRequest, RecordedRequest
from standin.redaction import NullRedactor

# Deterministic stand-in for a real embedder: a bag-of-words vector over a fixed
# vocabulary. Word order and punctuation drop out, meaning survives, no deps.
_VOCAB = ("summarize", "report", "quarterly", "please", "translate", "haiku", "french")


def _embed(text):
    tokens = re.findall(r"[a-z]+", text.lower())
    return [float(tokens.count(w)) for w in _VOCAB]


def _live(body):
    return RawRequest("POST", "http://x/v1", {"content-type": "application/json"}, json.dumps(body).encode())


def _stored(body):
    return RecordedRequest("POST", "http://x/v1", {}, {"json": body})


def _msg(content):
    return {"model": "gpt", "messages": [{"role": "user", "content": content}]}


def test_semantic_identical_body_matches():
    m = SemanticMatcher(_embed, NullRedactor())
    body = _msg("Summarize the quarterly report")
    assert m.matches(_live(body), _stored(body))


def test_semantic_paraphrase_above_threshold_matches():
    m = SemanticMatcher(_embed, NullRedactor(), threshold=0.95)
    a = _msg("Please summarize the quarterly report")
    b = _msg("Summarize the quarterly report, please.")
    assert m.matches(_live(a), _stored(b))


def test_semantic_rejects_unrelated_body():
    m = SemanticMatcher(_embed, NullRedactor(), threshold=0.95)
    a = _msg("Summarize the quarterly report")
    b = _msg("Translate this haiku into French")
    assert not m.matches(_live(a), _stored(b))


def test_semantic_url_must_still_match():
    m = SemanticMatcher(_embed, NullRedactor())
    live = RawRequest("POST", "http://x/a", {"content-type": "application/json"}, json.dumps(_msg("hi")).encode())
    stored = RecordedRequest("POST", "http://x/b", {}, {"json": _msg("hi")})
    assert not m.matches(live, stored)


def test_semantic_method_must_still_match():
    m = SemanticMatcher(_embed, NullRedactor(), match_on=("method", "body"))
    live = RawRequest("GET", "http://x/v1", {"content-type": "application/json"}, json.dumps(_msg("hi")).encode())
    stored = RecordedRequest("POST", "http://x/v1", {}, {"json": _msg("hi")})
    assert not m.matches(live, stored)


def test_semantic_zero_vector_does_not_match_a_different_body():
    # An embedder that returns a zero vector (e.g. for out-of-vocabulary text)
    # must not spuriously match: cosine is guarded to 0, below any threshold.
    m = SemanticMatcher(lambda _text: [0.0, 0.0, 0.0], NullRedactor(), threshold=0.5)
    a = _msg("Summarize the quarterly report")
    b = _msg("Translate this haiku into French")
    assert not m.matches(_live(a), _stored(b))
