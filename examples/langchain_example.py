"""standin with LangChain (langchain-openai).

standin hooks httpx, which LangChain's OpenAI client sends over, so wrapping the
chain call in use_cassette records and replays it with no changes to the chain.

    pytest examples/langchain_example.py
"""
import pytest

pytest.importorskip("langchain_openai")
from langchain_openai import ChatOpenAI  # noqa: E402

import standin  # noqa: E402


def test_langchain_replay(tmp_path):
    llm = ChatOpenAI(model="gpt-4o-mini")
    with standin.use_cassette(tmp_path / "langchain.json"):
        resp = llm.invoke("Say hello in exactly one word.")
    assert resp.content
