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


def _record_probe(llm_server):
    # An inner test that passes only when the run *recorded* (dirty is set), so
    # a passing outcome means "recorded" and a failing one means "replayed".
    return f'''
import httpx
import pytest

BODY = {{"model": "g", "messages": [{{"role": "user", "content": "hi"}}]}}

@pytest.mark.standin(path="shared.json")
def test_probe(standin):
    httpx.post("{llm_server.url}/v1/chat", json=BODY)
    assert standin.dirty
'''


def test_standin_mode_option_forces_record(pytester, llm_server):
    pytester.makepyfile(test_inner=_record_probe(llm_server))
    # First run: no cassette yet, default `once` records it.
    pytester.runpytest_inprocess("-p", "standin.pytest_plugin").assert_outcomes(passed=1)
    # Second run: cassette exists, default `once` replays -> not dirty -> fails.
    pytester.runpytest_inprocess("-p", "standin.pytest_plugin").assert_outcomes(failed=1)
    # --standin-mode=all re-records even though the cassette exists.
    result = pytester.runpytest_inprocess("-p", "standin.pytest_plugin", "--standin-mode=all")
    result.assert_outcomes(passed=1)


def test_standin_record_flag_forces_record(pytester, llm_server):
    pytester.makepyfile(test_inner=_record_probe(llm_server))
    pytester.runpytest_inprocess("-p", "standin.pytest_plugin").assert_outcomes(passed=1)
    pytester.runpytest_inprocess("-p", "standin.pytest_plugin").assert_outcomes(failed=1)
    # --standin-record is shorthand for --standin-mode=all.
    result = pytester.runpytest_inprocess("-p", "standin.pytest_plugin", "--standin-record")
    result.assert_outcomes(passed=1)


def test_standin_mode_option_beats_env(pytester, llm_server, monkeypatch):
    # STANDIN_MODE=none would refuse to record, but an explicit --standin-mode wins.
    monkeypatch.setenv("STANDIN_MODE", "none")
    pytester.makepyfile(test_inner=_record_probe(llm_server))
    result = pytester.runpytest_inprocess("-p", "standin.pytest_plugin", "--standin-mode=all")
    result.assert_outcomes(passed=1)


def test_marker_match_on_flows_through(pytester, llm_server):
    # The marker's match_on reaches the cassette: recorded with one body, replayed
    # with a different body, which only matches because body is excluded.
    pytester.makepyfile(
        test_inner=f'''
import httpx
import pytest

def _post(content):
    return httpx.post("{llm_server.url}/v1/chat",
                      json={{"model": "g", "messages": [{{"role": "user", "content": content}}]}})

@pytest.mark.standin(path="mo.json", match_on=["method", "url"], mode="all")
def test_record(standin):
    assert _post("one").status_code == 200

@pytest.mark.standin(path="mo.json", match_on=["method", "url"], mode="none")
def test_replay_with_a_different_body(standin):
    # Would miss under default (body-sensitive) matching; match_on ignores it.
    assert _post("TWO different body").status_code == 200
'''
    )
    result = pytester.runpytest_inprocess("-p", "standin.pytest_plugin")
    result.assert_outcomes(passed=2)
