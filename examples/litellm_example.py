"""standin with litellm.

    pytest examples/litellm_example.py -p standin.pytest_plugin

litellm calls providers over httpx, which standin hooks, so wrapping the call in
a cassette records it once and replays it offline, no per-provider wiring. First
run needs the provider key (e.g. OPENAI_API_KEY); every run after is free.
"""
import pytest

pytest.importorskip("litellm")
from litellm import completion  # noqa: E402


def summarize(text: str) -> str:
    resp = completion(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": f"Summarize in one line: {text}"}],
    )
    return resp.choices[0].message.content


@pytest.mark.standin  # cassette auto-named examples/cassettes/test_litellm_summarize.json
def test_litellm_summarize(standin):
    out = summarize("standin records LLM calls once and replays them forever.")
    assert isinstance(out, str) and out
