"""Public entry point: the use_cassette context manager."""
from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path

from . import matchers, patching
from .cassette import Cassette

VALID_MODES = {"once", "none", "all", "new_episodes"}


@contextmanager
def use_cassette(path, *, mode: str = "once", match_on=matchers.DEFAULT_MATCH_ON):
    """Record LLM/HTTP calls to `path`, or replay them if already recorded.

    Modes (like VCR):
      once          replay if the cassette exists, otherwise record (default)
      none          replay only; error on any unmatched call (use in CI)
      all           always re-record, ignoring existing interactions
      new_episodes  replay matches, record anything new

    Env override: UNDERSTUDY_MODE forces the mode for a whole run
    (handy for `UNDERSTUDY_MODE=none pytest` to guarantee no live calls).
    """
    mode = os.environ.get("UNDERSTUDY_MODE", mode)
    if mode not in VALID_MODES:
        raise ValueError(f"invalid mode {mode!r}; choose one of {sorted(VALID_MODES)}")

    path = Path(path)
    cassette = Cassette.load(path)
    session = patching.Session(cassette, mode, tuple(match_on))
    session.preexisting = len(cassette.interactions)

    patching.install()
    prev = patching.set_active(session)
    try:
        yield cassette
    finally:
        patching.clear_active(prev)
        cassette.save()
