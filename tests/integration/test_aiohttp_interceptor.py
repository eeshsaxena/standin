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


def test_error_status_replayed_and_raises_for_status(llm_server, tmp_path):
    cassette = tmp_path / "aio_err.json"
    url = llm_server.url + "/v1/error"

    async def record():
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json={"x": 1}) as resp:
                return resp.status, await resp.json()

    with standin.use_cassette(cassette):
        status, body = _run(record())
    assert status == 429

    llm_server.stop()

    async def replay():
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json={"x": 1}) as resp:
                assert resp.status == 429
                with pytest.raises(aiohttp.ClientResponseError):
                    resp.raise_for_status()
                return await resp.json()

    with standin.use_cassette(cassette):
        assert _run(replay()) == body


def test_headers_preserved_on_replay(llm_server, tmp_path):
    cassette = tmp_path / "aio_hdr.json"
    url = llm_server.url + "/v1/chat/completions"
    payload = {"model": "gpt", "messages": [{"role": "user", "content": "hi"}]}

    async def call():
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                return resp.headers.get("Content-Type"), await resp.json()

    with standin.use_cassette(cassette):
        recorded_ct, _ = _run(call())

    llm_server.stop()

    with standin.use_cassette(cassette):
        replayed_ct, _ = _run(call())
    assert replayed_ct == recorded_ct
    assert "application/json" in replayed_ct


def test_data_bytes_body_records_and_replays(llm_server, tmp_path):
    # A `data=` bytes payload (not json=) exercises the bytes request path.
    cassette = tmp_path / "aio_data.json"
    url = llm_server.url + "/v1/text"

    async def call():
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=b"raw bytes body") as resp:
                return await resp.text()

    with standin.use_cassette(cassette):
        recorded = _run(call())

    llm_server.stop()

    with standin.use_cassette(cassette):
        assert _run(call()) == recorded
