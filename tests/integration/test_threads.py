"""Thread isolation: concurrent cassettes must not cross-contaminate."""
from __future__ import annotations

import threading

import httpx

import standin


def test_concurrent_cassettes_are_isolated(tmp_path, llm_server):
    n = 4
    barrier = threading.Barrier(n)
    recorded: dict[int, str] = {}

    def record(i):
        body = {"model": "g", "messages": [{"role": "user", "content": f"thread-{i}"}]}
        barrier.wait()  # maximize overlap
        with standin.use_cassette(tmp_path / f"t{i}.json", mode="all"):
            r = httpx.post(f"{llm_server.url}/v1/chat", json=body)
            recorded[i] = r.json()["id"]

    threads = [threading.Thread(target=record, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(set(recorded.values())) == n  # each thread got its own live response

    llm_server.stop()
    for i in range(n):
        body = {"model": "g", "messages": [{"role": "user", "content": f"thread-{i}"}]}
        with standin.use_cassette(tmp_path / f"t{i}.json", mode="none"):
            r = httpx.post(f"{llm_server.url}/v1/chat", json=body)
        assert r.json()["id"] == recorded[i]  # each cassette holds only its own call
