"""Interceptor abstraction + the active-engine context.

An interceptor knows how to splice into one HTTP client and translate its calls
into the engine's transport-neutral interface. The active engine is stored in a
``ContextVar`` so recording is correct under threads and asyncio, and so the
patch stays inert whenever no cassette is open.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from contextvars import ContextVar, Token

from ..engine import Engine

_active_engine: ContextVar[Engine | None] = ContextVar("standin_active_engine", default=None)


def get_active_engine() -> Engine | None:
    return _active_engine.get()


def set_active_engine(engine: Engine) -> Token:
    return _active_engine.set(engine)


def reset_active_engine(token: Token) -> None:
    _active_engine.reset(token)


class Interceptor(ABC):
    """Splices into an HTTP client and routes its traffic through the engine."""

    @abstractmethod
    def install(self) -> None:
        """Patch the client. Must be idempotent and inert with no active engine."""
