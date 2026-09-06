"""standin with the OpenAI SDK.

    pytest examples/openai_example.py -p standin.pytest_plugin

First run records against the real API (needs OPENAI_API_KEY); every run after
replays from examples/cassettes/, offline, free, and deterministic. Nothing about
your code changes; you only wrap the test.
"""
import pytest

pytest.importorskip("openai")
from openai import OpenAI  # noqa: E402


def summarize(text: str) -> str:
    resp = OpenAI().chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": f"Summarize in one line: {text}"}],
    )
    return resp.choices[0].message.content


@pytest.mark.standin  # cassette auto-named examples/cassettes/test_summarize.json
def test_summarize(standin):
    out = summarize("standin records LLM calls once and replays them forever.")
    assert isinstance(out, str) and out
