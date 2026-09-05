"""understudy — a stand-in for the real LLM in your tests.

Record real LLM API calls once, then replay them forever: fast, free, offline,
and deterministic. Provider-agnostic (hooks httpx), streaming and tool-calls
supported, and secrets are redacted so cassettes are safe to commit.

    import understudy

    with understudy.use_cassette("tests/cassettes/summary.json"):
        resp = openai_client.chat.completions.create(...)   # recorded once, replayed after
"""
from .cassette import Cassette
from .core import use_cassette
from .patching import CannotReplay

__version__ = "0.1.0"
__all__ = ["use_cassette", "Cassette", "CannotReplay", "__version__"]
