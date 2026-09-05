"""In-memory cassette: the interactions plus the replay cursor."""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path

from .models import Interaction


@dataclass
class Cassette:
    path: Path
    interactions: list[Interaction] = field(default_factory=list)
    dirty: bool = False
    preexisting: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    def __post_init__(self):
        self.preexisting = len(self.interactions)

    def append(self, interaction: Interaction) -> None:
        with self._lock:
            self.interactions.append(interaction)
            self.dirty = True

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
