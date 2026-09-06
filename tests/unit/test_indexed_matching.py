"""The O(1) indexed path must return exactly what the linear scan returns.

DefaultMatcher's match is `live_key(live) == stored_key(stored)`, so
`Cassette.find_unplayed_indexed` (per-key queues) and `Cassette.find_unplayed`
(the linear scan) have to agree on every sequence of requests.
"""
from __future__ import annotations

import json
import random

from standin.cassette import Cassette
from standin.config import Config
from standin.engine import Engine
from standin.matching import DefaultMatcher, FuzzyMatcher
from standin.models import (
    Interaction,
    Mode,
    RawRequest,
    RecordedRequest,
    RecordedResponse,
)
from standin.redaction import NullRedactor

MATCHER = DefaultMatcher(NullRedactor())


def _rec(q, rid):
    # A recorded interaction whose request body is {"q": q}; rid tags the response
    # so we can tell which recording was played back.
    return Interaction(
        request=RecordedRequest("POST", "http://x", {}, {"json": {"q": q}}),
        response=RecordedResponse(200, {}, {"json": {"rid": rid}}),
    )


def _live(q):
    body = json.dumps({"q": q}).encode()
    return RawRequest("POST", "http://x", {"content-type": "application/json"}, body)


def _rid(interaction):
    return None if interaction is None else interaction.response.body["json"]["rid"]


def _replay_linear(interactions, queries):
    c = Cassette(path="x", interactions=[_rec(q, i) for q, i in interactions])
    return [_rid(c.find_unplayed(MATCHER.matches, _live(q))) for q in queries]


def _replay_indexed(interactions, queries):
    c = Cassette(path="x", interactions=[_rec(q, i) for q, i in interactions])
    return [
        _rid(c.find_unplayed_indexed(MATCHER.live_key, MATCHER.stored_key, _live(q)))
        for q in queries
    ]


def test_repeats_replay_in_recorded_order_then_exhaust():
    interactions = [("same", 0), ("same", 1)]
    queries = ["same", "same", "same"]
    assert _replay_indexed(interactions, queries) == [0, 1, None]
    assert _replay_indexed(interactions, queries) == _replay_linear(interactions, queries)


def test_interleaved_distinct_keys():
    interactions = [("a", 0), ("b", 1), ("a", 2)]
    queries = ["a", "b", "a", "a"]  # third 'a' exhausts
    assert _replay_indexed(interactions, queries) == [0, 1, 2, None]
    assert _replay_indexed(interactions, queries) == _replay_linear(interactions, queries)


def test_non_matching_request_misses():
    interactions = [("a", 0)]
    assert _replay_indexed(interactions, ["missing"]) == [None]
    assert _replay_indexed(interactions, ["missing"]) == _replay_linear(interactions, ["missing"])


def test_empty_cassette_misses():
    assert _replay_indexed([], ["anything"]) == [None]


def test_record_then_replay_keeps_index_consistent():
    # Index built on the first (missing) lookup, then a fresh recording is appended
    # and must be findable without a rebuild — the new_episodes path.
    c = Cassette(path="x", interactions=[_rec("old", 0)])
    assert _rid(c.find_unplayed_indexed(MATCHER.live_key, MATCHER.stored_key, _live("new"))) is None
    c.append(_rec("new", 1))
    assert _rid(c.find_unplayed_indexed(MATCHER.live_key, MATCHER.stored_key, _live("new"))) == 1
    # and the old recording still replays exactly once
    assert _rid(c.find_unplayed_indexed(MATCHER.live_key, MATCHER.stored_key, _live("old"))) == 0
    assert _rid(c.find_unplayed_indexed(MATCHER.live_key, MATCHER.stored_key, _live("old"))) is None


def test_append_before_first_lookup_is_indexed_on_build():
    # If nothing has been looked up yet the index is still None; the append must
    # show up when the index is built lazily on the first lookup.
    c = Cassette(path="x", interactions=[_rec("a", 0)])
    c.append(_rec("a", 1))
    got = [
        _rid(c.find_unplayed_indexed(MATCHER.live_key, MATCHER.stored_key, _live("a")))
        for _ in range(3)
    ]
    assert got == [0, 1, None]


def test_random_sequences_match_linear_scan():
    rng = random.Random(1234)
    keys = ["a", "b", "c", "d", "miss"]
    for _ in range(300):
        n = rng.randint(0, 12)
        # 'miss' is never recorded, so it always misses in both paths.
        interactions = [(rng.choice(keys[:-1]), i) for i in range(n)]
        queries = [rng.choice(keys) for _ in range(rng.randint(0, 16))]
        assert _replay_indexed(interactions, queries) == _replay_linear(interactions, queries)


def _no_network(_request):
    raise AssertionError("network was called in replay-only mode")


def test_engine_default_matcher_uses_the_index():
    # Replaying through the engine with the default (keyed) matcher builds the index.
    cassette = Cassette(path="x", interactions=[_rec("a", 0)])
    engine = Engine(cassette, Config(mode=Mode.NONE, redact=False))
    resp = engine.handle(_live("a"), _no_network)
    assert resp.status_code == 200
    assert cassette._index is not None  # keyed path was taken


def test_engine_fuzzy_matcher_stays_linear():
    # A matcher without live_key/stored_key must never build the index.
    cassette = Cassette(path="x", interactions=[_rec("a", 0)])
    matcher = FuzzyMatcher(NullRedactor())
    engine = Engine(cassette, Config(mode=Mode.NONE, redact=False, matcher=matcher))
    engine.handle(_live("a"), _no_network)
    assert cassette._index is None  # linear scan, no index built


def test_match_on_subset_keys_agree():
    # With body excluded, distinct bodies share a key and replay in recorded order.
    matcher = DefaultMatcher(NullRedactor(), match_on=("method", "url"))
    c_lin = Cassette(path="x", interactions=[_rec("a", 0), _rec("b", 1)])
    c_idx = Cassette(path="x", interactions=[_rec("a", 0), _rec("b", 1)])
    queries = ["a", "zzz", "qqq"]
    linear = [_rid(c_lin.find_unplayed(matcher.matches, _live(q))) for q in queries]
    indexed = [
        _rid(c_idx.find_unplayed_indexed(matcher.live_key, matcher.stored_key, _live(q)))
        for q in queries
    ]
    assert linear == indexed == [0, 1, None]
