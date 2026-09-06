"""Replay-lookup benchmark: the O(1) key index vs. the linear scan.

The default matcher's match is `live_key(live) == stored_key(stored)`, so a
cassette can index its interactions by key and pop the next one for a request in
O(1). The old path scans the interaction list on every request, which is O(n) per
request and O(n^2) to replay a whole cassette.

This times a full in-order replay of a large cassette both ways and prints the
speedup. In-order replay is the realistic case (a test or agent loop replays the
calls it recorded, in order) and it is the *kindest* case for the linear scan (the
already-played prefix is skipped cheaply), so the number here is honest, not
cherry-picked. Only the cassette lookup is measured; there is no network or
decoding in replay. Run: `python benchmarks/bench_matching.py [n]`.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # run without installing

from standin.cassette import Cassette  # noqa: E402
from standin.matching import DefaultMatcher  # noqa: E402
from standin.models import Interaction, RawRequest, RecordedRequest, RecordedResponse  # noqa: E402
from standin.redaction import NullRedactor  # noqa: E402

MATCHER = DefaultMatcher(NullRedactor())


def _interactions(n: int) -> list[Interaction]:
    # n distinct requests, each recorded once (distinct bodies -> distinct keys).
    return [
        Interaction(
            request=RecordedRequest("POST", "https://api.example/v1/chat", {}, {"json": {"i": i}}),
            response=RecordedResponse(200, {}, {"json": {"reply": i}}),
        )
        for i in range(n)
    ]


def _live_requests(n: int) -> list[RawRequest]:
    ct = {"content-type": "application/json"}
    return [RawRequest("POST", "https://api.example/v1/chat", ct, json.dumps({"i": i}).encode()) for i in range(n)]


def _time_linear(interactions: list[Interaction], live: list[RawRequest]) -> tuple[float, int]:
    cassette = Cassette(path="bench", interactions=[_clone(i) for i in interactions])
    start = perf_counter()
    hits = sum(cassette.find_unplayed(MATCHER.matches, req) is not None for req in live)
    return perf_counter() - start, hits


def _time_indexed(interactions: list[Interaction], live: list[RawRequest]) -> tuple[float, int]:
    cassette = Cassette(path="bench", interactions=[_clone(i) for i in interactions])
    start = perf_counter()
    hits = sum(
        cassette.find_unplayed_indexed(MATCHER.live_key, MATCHER.stored_key, req) is not None
        for req in live
    )
    return perf_counter() - start, hits


def _clone(interaction: Interaction) -> Interaction:
    # Fresh interaction (played=False) so each trial starts from a clean cassette.
    return Interaction(request=interaction.request, response=interaction.response)


def _best(fn, interactions, live, trials: int = 3) -> tuple[float, int]:
    best = float("inf")
    hits = 0
    for _ in range(trials):
        elapsed, hits = fn(interactions, live)
        best = min(best, elapsed)
    return best, hits


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    interactions = _interactions(n)
    live = _live_requests(n)

    linear, linear_hits = _best(_time_linear, interactions, live)
    indexed, indexed_hits = _best(_time_indexed, interactions, live)

    assert linear_hits == indexed_hits == n, (linear_hits, indexed_hits, n)
    speedup = linear / indexed if indexed else float("inf")

    print(f"cassette: {n} interactions, full in-order replay (best of 3)")
    print(f"  linear scan : {linear * 1e3:8.1f} ms  ({linear / n * 1e6:6.1f} us/request)")
    print(f"  key index   : {indexed * 1e3:8.1f} ms  ({indexed / n * 1e6:6.1f} us/request)")
    print(f"  speedup     : {speedup:6.1f}x")


if __name__ == "__main__":
    main()
