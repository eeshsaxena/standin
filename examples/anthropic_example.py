"""standin with the Anthropic SDK.

    pytest examples/anthropic_example.py -p standin.pytest_plugin

First run records against the real API (needs ANTHROPIC_API_KEY); every run after
replays from tests/cassettes/ — offline, free, deterministic. Nothing about your
code changes; you only wrap the test.
"""
import pytest

pytest.importorskip("anthropic")
from anthropic import Anthropic  # noqa: E402


def haiku(topic: str) -> str:
    resp = Anthropic().messages.create(
        model="claude-3-haiku-20240307",
        max_tokens=64,
        messages=[{"role": "user", "content": f"Write a haiku about {topic}."}],
    )
    return resp.content[0].text


@pytest.mark.standin  # cassette auto-named examples/cassettes/test_haiku.json
def test_haiku(standin):
    out = haiku("deterministic tests")
    assert isinstance(out, str) and out
