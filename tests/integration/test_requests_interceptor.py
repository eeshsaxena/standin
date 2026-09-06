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
