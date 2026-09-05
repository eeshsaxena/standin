"""Configuration object wiring the pluggable pieces together."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from .exceptions import ConfigError
from .matching import DEFAULT_MATCH_ON, Matcher
from .models import Mode
from .redaction import DefaultRedactor, NullRedactor, Redactor
from .storage import CassetteStore, JSONCassetteStore


@dataclass
class Config:
    mode: Mode = Mode.ONCE
    match_on: Sequence[str] = DEFAULT_MATCH_ON
    redact: bool = True
    redactor: Redactor | None = None
    matcher: Matcher | None = None
    store: CassetteStore = field(default_factory=JSONCassetteStore)

    def __post_init__(self):
        if not isinstance(self.mode, Mode):
            try:
                self.mode = Mode(self.mode)
            except ValueError as exc:
                raise ConfigError(
                    f"invalid mode {self.mode!r}; choose one of {[m.value for m in Mode]}"
                ) from exc
        if self.redactor is None:
            self.redactor = DefaultRedactor() if self.redact else NullRedactor()
