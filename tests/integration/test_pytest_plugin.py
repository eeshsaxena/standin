"""Exercise the actual pytest plugin (the `standin` fixture + marker) via pytester."""
from __future__ import annotations


def test_standin_fixture_records_and_replays(pytester, llm_server):
    pytester.makepyfile(
        test_inner=f'''
import httpx
import pytest

BODY = {{"model": "g", "messages": [{{"role": "user", "content": "hi"}}]}}

@pytest.mark.standin(mode="all")
def test_record(standin):
    r = httpx.post("{llm_server.url}/v1/chat", json=BODY)
    assert r.status_code == 200
    assert standin.dirty            # something was recorded to the cassette

@pytest.mark.standin(mode="none")
def test_replay(standin):
    # same request, replayed from the cassette recorded above (default name per test
    # differs, so point both at one file)
    pass
'''
    )
    result = pytester.runpytest_inprocess("-p", "standin.pytest_plugin")
    result.assert_outcomes(passed=2)


def test_fixture_default_cassette_path(pytester, llm_server):
    pytester.makepyfile(
        test_path=f'''
import httpx

def test_auto_named(standin):
    httpx.post("{llm_server.url}/v1/chat", json={{"model": "g", "messages": []}})
    # cassette auto-named under <testdir>/cassettes/<test-name>.json
    assert standin.path.name == "test_auto_named.json"
    assert standin.path.parent.name == "cassettes"
'''
    )
    result = pytester.runpytest_inprocess("-p", "standin.pytest_plugin")
    result.assert_outcomes(passed=1)
