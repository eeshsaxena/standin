"""pytest integration: an `understudy` fixture and an `@pytest.mark.understudy` marker.

Cassettes default to `<test-dir>/cassettes/<test-name>.json`. First run records,
later runs replay. In CI, set UNDERSTUDY_MODE=none to fail on any un-recorded call.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from .core import use_cassette


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "understudy(path=None, mode='once', match_on=None): record/replay LLM HTTP calls for this test",
    )


@pytest.fixture
def understudy(request):
    marker = request.node.get_closest_marker("understudy")
    opts = dict(marker.kwargs) if marker else {}

    name = opts.get("path") or f"{request.node.name}.json"
    path = Path(name)
    if not path.is_absolute():
        path = Path(request.node.fspath).parent / "cassettes" / path

    kwargs = {"mode": opts.get("mode", "once")}
    if opts.get("match_on"):
        kwargs["match_on"] = opts["match_on"]

    with use_cassette(path, **kwargs) as cassette:
        yield cassette
