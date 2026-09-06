"""In-memory cassette: the interactions plus the replay cursor."""
from __future__ import annotations

import threading
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from .models import Interaction, RecordedRequest


@dataclass
class Cassette:
    path: Path
    interactions: list[Interaction] = field(default_factory=list)
    dirty: bool = False
    preexisting: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)
    # Lazily built by find_unplayed_indexed for key-based matchers: stored_key ->
    # queue of not-yet-played interactions in recorded order. None until first use.
    _index: dict[str, deque[Interaction]] | None = field(default=None, repr=False, compare=False)
    _stored_key: Callable[[RecordedRequest], str] | None = field(
        default=None, repr=False, compare=False
    )

    def __post_init__(self):
        self.preexisting = len(self.interactions)

    def append(self, interaction: Interaction) -> None:
        with self._lock:
            self.interactions.append(interaction)
            self.dirty = True
            # Keep the index in step so a recorded-then-replayed call (new_episodes)
            # is findable without a rebuild.
            if self._index is not None and self._stored_key is not None:
                self._index.setdefault(self._stored_key(interaction.request), deque()).append(
                    interaction
                )

    def find_unplayed(self, matches, live_request) -> Interaction | None:
        """Return the first not-yet-played interaction that matches the request.

        `matches(live_request, stored_request) -> bool` is supplied by the
        matcher, so exact and fuzzy strategies share this loop. Playing in order
        lets repeated calls (e.g. an agent loop) replay their distinct recorded
        responses sequentially. Locked so a shared cassette never double-plays.
        """
        with self._lock:
            for interaction in self.interactions:
                if not interaction.played and matches(live_request, interaction.request):
                    interaction.played = True
                    return interaction
        return None

    def find_unplayed_indexed(self, live_key, stored_key, live_request) -> Interaction | None:
        """O(1) equivalent of find_unplayed for key-based matchers (DefaultMatcher).

        The matcher's match is exactly `live_key(live) == stored_key(stored)`, so
        instead of scanning we keep a per-key queue of not-yet-played interactions
        in recorded order and pop the next one for the live request's key. Same
        result as the linear scan (repeats replay in recorded order, each once,
        misses return None), but without walking every interaction. Locked the same
        way, so a shared cassette never double-plays.
        """
        key = live_key(live_request)
        with self._lock:
            if self._index is None:
                self._build_index(stored_key)
            queue = self._index.get(key) if self._index is not None else None
            while queue:
                interaction = queue.popleft()
                if not interaction.played:  # skip anything already played elsewhere
                    interaction.played = True
                    return interaction
        return None

    def _build_index(self, stored_key: Callable[[RecordedRequest], str]) -> None:
        """Build the stored_key -> queue index over the current interactions.

        Caller holds the lock. Only unplayed interactions are queued, in recorded
        order, so the index matches what a linear scan would still return.
        """
        index: dict[str, deque[Interaction]] = {}
        for interaction in self.interactions:
            if not interaction.played:
                index.setdefault(stored_key(interaction.request), deque()).append(interaction)
        self._index = index
        self._stored_key = stored_key
