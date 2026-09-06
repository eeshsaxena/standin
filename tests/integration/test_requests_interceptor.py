"""The requests interceptor records and replays real `requests` traffic."""
from __future__ import annotations

import requests

import standin


def test_record_then_replay_returns_same_body(llm_server, tmp_path):
    cassette = tmp_path / "req.json"
    url = llm_server.url + "/v1/chat/completions"
    payload = {"model": "gpt", "messages": [{"role": "user", "content": "hi"}]}

    with standin.use_cassette(cassette):
        first = requests.post(url, json=payload)
        first_body = first.json()
    assert first.status_code == 200
    assert cassette.exists()

    # The test server bumps a counter per call, so a fresh live call would differ.
    # Replay must return the recorded body instead.
    with standin.use_cassette(cassette):
        second = requests.post(url, json=payload)
    assert second.status_code == 200
    assert second.json() == first_body


def test_replay_works_with_the_server_gone(llm_server, tmp_path):
    cassette = tmp_path / "text.json"
    url = llm_server.url + "/v1/text"

    with standin.use_cassette(cassette):
        recorded_text = requests.post(url, json={"q": 1}).text

    llm_server.stop()  # prove replay is fully offline

    with standin.use_cassette(cassette):
        replayed = requests.post(url, json={"q": 1})
    assert replayed.text == recorded_text
    assert replayed.status_code == 200


def test_error_status_recorded_and_replayed(llm_server, tmp_path):
    cassette = tmp_path / "err.json"
    url = llm_server.url + "/v1/error"

    with standin.use_cassette(cassette, mode="all"):
        first = requests.post(url, json={"x": 1})
    assert first.status_code == 429
    body = first.json()

    llm_server.stop()
    with standin.use_cassette(cassette, mode="none"):
        second = requests.post(url, json={"x": 1})
    assert second.status_code == 429
    assert second.json() == body


def test_string_body_records_and_replays(llm_server, tmp_path):
    # A str `data=` payload (not json=) exercises the str-encoding request path.
    cassette = tmp_path / "strbody.json"
    url = llm_server.url + "/v1/text"

    with standin.use_cassette(cassette, mode="all"):
        recorded = requests.post(url, data="raw string body").text
    llm_server.stop()
    with standin.use_cassette(cassette, mode="none"):
        assert requests.post(url, data="raw string body").text == recorded


def test_streamed_and_absent_bodies_canonicalize_to_empty():
    # A generator/file-like body can't be canonicalized, and neither can an absent
    # one; both are treated as empty rather than raising.
    from standin.interceptors.requests_interceptor import _to_raw_request

    prepared = requests.Request("POST", "http://x/v1", data=iter([b"a", b"b"])).prepare()
    assert _to_raw_request(prepared).body == b""

    no_body = requests.Request("GET", "http://x/v1").prepare()
    assert _to_raw_request(no_body).body == b""


def test_passthrough_without_cassette_is_a_live_call(llm_server, tmp_path):
    # Warm up so the adapter is patched, then call with no cassette open: the hook
    # must fall straight through to the real send.
    with standin.use_cassette(tmp_path / "warm.json", mode="all"):
        pass
    resp = requests.post(llm_server.url + "/v1/text", json={"q": 1})
    assert resp.status_code == 200
