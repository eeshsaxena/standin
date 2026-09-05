"""Demo: three LLM-backed tests. First run records; every run after replays.

Run it twice to feel the difference:
    pytest demo/test_summary.py -p standin.pytest_plugin -q   # records (slow)
    pytest demo/test_summary.py -p standin.pytest_plugin -q   # replays (instant, offline, free)
"""
from __future__ import annotations

import pytest
from openai import OpenAI


def summarize(text: str) -> str:
    resp = OpenAI().chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": f"Summarize in one line: {text}"}],
    )
    return resp.choices[0].message.content


@pytest.mark.standin
def test_summarize_release_notes(standin):
    assert summarize("We shipped dark mode, faster search, and 12 bug fixes.")


@pytest.mark.standin
def test_summarize_support_ticket(standin):
    assert summarize("Customer cannot log in after the latest update on iOS.")


@pytest.mark.standin
def test_summarize_meeting(standin):
    assert summarize("The team agreed to move the launch to Q3 and hire two engineers.")
