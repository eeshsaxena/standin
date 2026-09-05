"""Async httpx path (the interceptor's handle_async), incl. concurrency."""
from __future__ import annotations

import asyncio

import httpx
import pytest

import standin


def test_async_record_then_replay(tmp_path, llm_server):
    cass = tmp_path / "async.json"
    payload = {"model": "gpt", "messages": [{"role": "user", "content": "hi"}]}

    async def go(url):
        async with httpx.AsyncClient() as c:
            r = await c.post(f"{url}/v1/chat", json=payload)
            return r.json()["choices"][0]["message"]["content"]

    with standin.use_cassette(cass, mode="all"):
        recorded = asyncio.run(go(llm_server.url))
    llm_server.stop()
    with standin.use_cassette(cass, mode="none"):
        replayed = asyncio.run(go(llm_server.url))
    assert replayed == recorded


def test_async_concurrent_calls(tmp_path, llm_server):
    cass = tmp_path / "async_concurrent.json"

    def payload(i):
        return {"model": "gpt", "messages": [{"role": "user", "content": f"q{i}"}]}

    async def many(url, n):
        async with httpx.AsyncClient() as c:
            results = await asyncio.gather(*[c.post(f"{url}/v1/chat", json=payload(i)) for i in range(n)])
            return [r.json()["choices"][0]["message"]["content"] for r in results]

    with standin.use_cassette(cass, mode="all"):
        recorded = asyncio.run(many(llm_server.url, 6))
    llm_server.stop()
    with standin.use_cassette(cass, mode="none"):
        replayed = asyncio.run(many(llm_server.url, 6))
    assert sorted(replayed) == sorted(recorded)
    assert len(set(replayed)) == 6  # distinct bodies -> distinct recordings


def test_async_replay_only_miss_raises(tmp_path):
    cass = tmp_path / "empty.json"

    async def go():
        async with httpx.AsyncClient() as c:
            await c.post("http://127.0.0.1:1/v1/chat", json={"x": 1})

    with standin.use_cassette(cass, mode="none"):
        with pytest.raises(standin.CannotReplay):
            asyncio.run(go())


def test_async_inert_passthrough_without_cassette(tmp_path, llm_server):
    with standin.use_cassette(tmp_path / "warm.json", mode="all"):
        pass  # ensure the async patch is installed

    async def go(url):
        async with httpx.AsyncClient() as c:
            r = await c.post(f"{url}/v1/chat", json={"model": "g", "messages": []})
            return r.status_code

    assert asyncio.run(go(llm_server.url)) == 200
