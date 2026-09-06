"""standin: a stand-in for the real LLM in your tests.

Record real LLM API calls once, then replay them forever: fast, free, offline,
and deterministic. Provider-agnostic (hooks httpx, requests, and aiohttp),
streaming and tool-calls supported, secrets redacted so cassettes are safe to
commit.

    import standin

    with standin.use_cassette("tests/cassettes/summary.json"):
        resp = openai_client.chat.completions.create(...)   # recorded once, replayed after

Architecture (see ARCHITECTURE.md): a transport-neutral policy **engine** sits
behind pluggable **interceptors** (httpx, requests, aiohttp), **matchers**,
**redactors**, and **stores**, so behavior is easy to reason about and extend.
"""
from .config import Config
from .core import use_cassette
from .exceptions import CannotReplay, CassetteError, ConfigError, StandinError
from .matching import DefaultMatcher, FuzzyMatcher, Matcher, SemanticMatcher
from .models import Mode
from .redaction import DefaultRedactor, NullRedactor, Redactor
from .storage import CassetteStore, JSONCassetteStore

__version__ = "0.7.1"
__all__ = [
    "use_cassette",
    "Config",
    "Mode",
    "StandinError",
    "CannotReplay",
    "CassetteError",
    "ConfigError",
    "Redactor",
    "DefaultRedactor",
    "NullRedactor",
    "Matcher",
    "DefaultMatcher",
    "FuzzyMatcher",
    "SemanticMatcher",
    "CassetteStore",
    "JSONCassetteStore",
    "__version__",
]
