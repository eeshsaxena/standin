"""Exception hierarchy for standin.

All errors derive from :class:`StandinError` so callers can catch the whole
library with a single ``except``.
"""
from __future__ import annotations


class StandinError(Exception):
    """Base class for every error raised by standin."""


class ConfigError(StandinError):
    """Invalid configuration (bad mode, conflicting options, ...)."""


class CassetteError(StandinError):
    """A cassette file is missing, malformed, or on an unsupported version."""


class CannotReplay(StandinError):
    """Replay-only mode encountered a request with no matching recording."""
