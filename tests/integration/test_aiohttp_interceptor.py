"""The aiohttp interceptor records and replays real aiohttp traffic.

Skipped where aiohttp isn't importable (e.g. no yarl wheel on very new Pythons);
runs in CI on the supported matrix.
"""
from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("aiohttp")
import aiohttp  # noqa: E402

import standin  # noqa: E402


def _run(coro):
    return asyncio.run(coro)


def test_record_then_replay_returns_same_json(llm_server, tmp_path):
    cassette = tmp_path / "aio.json"
    url = llm_server.url + "/v1/chat/completions"
    payload = {"model": "gpt", "messages": [{"role": "user", "content": "hi"}]}

    async def call():
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                return resp.status, await resp.json()

    with standin.use_cassette(cassette):
        status1, body1 = _run(call())
    assert status1 == 200
    assert cassette.exists()

    with standin.use_cassette(cassette):
        status2, body2 = _run(call())
    assert status2 == 200
    assert body2 == body1


def test_replay_offline_and_text(llm_server, tmp_path):
    cassette = tmp_path / "aio_text.json"
    url = llm_server.url + "/v1/text"

    async def call():
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json={"q": 1}) as resp:
                return await resp.text()

    with standin.use_cassette(cassette):
        recorded = _run(call())

    llm_server.stop()  # replay must not touch the network

    with standin.use_cassette(cassette):
        replayed = _run(call())
    assert replayed == recorded
