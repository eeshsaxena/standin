"""Public entry point: the ``use_cassette`` context manager."""
from __future__ import annotations

import os
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path

from .cassette import Cassette
from .config import Config
from .engine import Engine
from .exceptions import ConfigError
from .interceptors.base import reset_active_engine, set_active_engine
from .interceptors.httpx_interceptor import HttpxInterceptor
from .matching import DEFAULT_MATCH_ON, Matcher
from .models import Mode
from .redaction import Redactor
from .storage import CassetteStore

_httpx_interceptor = HttpxInterceptor()


@contextmanager
def use_cassette(
    path,
    *,
    mode: str = "once",
    match_on: Sequence[str] = DEFAULT_MATCH_ON,
    redact: bool = True,
    redactor: Redactor | None = None,
    matcher: Matcher | None = None,
    store: CassetteStore | None = None,
) -> Iterator[Cassette]:
    """Record LLM/HTTP calls to ``path``, or replay them if already recorded.

    The environment variable ``STANDIN_MODE`` overrides ``mode`` for a whole run
    (e.g. ``STANDIN_MODE=none pytest`` guarantees no live calls in CI).
    """
    mode = os.environ.get("STANDIN_MODE", mode)
    try:
        mode_value = mode if isinstance(mode, Mode) else Mode(mode)
    except ValueError as exc:
        raise ConfigError(
            f"invalid mode {mode!r}; choose one of {[m.value for m in Mode]}"
        ) from exc

    config = Config(
        mode=mode_value,
        match_on=match_on,
        redact=redact,
        redactor=redactor,
        matcher=matcher,
    )
    if store is not None:
        config.store = store

    path = Path(path)
    cassette = Cassette(path=path, interactions=config.store.load(path))
    engine = Engine(cassette, config)

    _httpx_interceptor.install()
    token = set_active_engine(engine)
    try:
        yield cassette
    finally:
        reset_active_engine(token)
        if cassette.dirty:
            config.store.save(path, cassette.interactions)
