"""pytest integration: a ``standin`` fixture and a ``@pytest.mark.standin`` marker.

Cassettes default to ``<test-dir>/cassettes/<test-name>.json``. First run records;
later runs replay. In CI, set ``STANDIN_MODE=none`` to fail on any un-recorded call.

The mode can also be driven from the command line, which wins over both the
marker and ``STANDIN_MODE``::

    pytest --standin-mode=none    # replay-only for the whole run
    pytest --standin-record       # shorthand for --standin-mode=all
"""
from __future__ import annotations

from pathlib import Path

import pytest

from .core import use_cassette
from .models import Mode


def pytest_addoption(parser):
    group = parser.getgroup("standin", "record/replay of LLM HTTP calls")
    group.addoption(
        "--standin-mode",
        action="store",
        default=None,
        choices=[m.value for m in Mode],
        help="mode for cassettes opened by the standin fixture/marker; "
             "overrides STANDIN_MODE for the run (once, none, all, new_episodes)",
    )
    group.addoption(
        "--standin-record",
        action="store_true",
        default=False,
        help="shorthand for --standin-mode=all (re-record every cassette)",
    )


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "standin(path=None, mode='once', match_on=None): record/replay LLM HTTP calls for this test",
    )


def _cli_mode(config) -> str | None:
    if config.getoption("--standin-record"):
        return Mode.ALL.value
    return config.getoption("--standin-mode")


@pytest.fixture
def standin(request, monkeypatch):
    marker = request.node.get_closest_marker("standin")
    opts = dict(marker.kwargs) if marker else {}

    name = opts.get("path") or f"{request.node.name}.json"
    path = Path(name)
    if not path.is_absolute():
        path = Path(request.node.fspath).parent / "cassettes" / path

    kwargs = {}
    if opts.get("match_on"):
        kwargs["match_on"] = opts["match_on"]

    cli_mode = _cli_mode(request.config)
    if cli_mode is not None:
        # An explicit command-line mode wins over the marker and STANDIN_MODE:
        # clear the env override for this test so the chosen mode stands.
        monkeypatch.delenv("STANDIN_MODE", raising=False)
        kwargs["mode"] = cli_mode
    else:
        kwargs["mode"] = opts.get("mode", "once")

    with use_cassette(path, **kwargs) as cassette:
        yield cassette
