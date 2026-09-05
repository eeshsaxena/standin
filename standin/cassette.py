"""In-memory cassette: the interactions plus the replay cursor."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .models import Interaction


@dataclass
class Cassette:
    path: Path
    interactions: list[Interaction] = field(default_factory=list)
    dirty: bool = False
    preexisting: int = 0

    def __post_init__(self):
        self.preexisting = len(self.interactions)

    def append(self, interaction: Interaction) -> None:
        self.interactions.append(interaction)
        self.dirty = True

    def find_unplayed(self, stored_key_fn, live_key: str) -> Interaction | None:
        """Return the first not-yet-played interaction whose key matches.

        Playing in order lets repeated identical calls (e.g. an agent loop)
        replay their distinct recorded responses sequentially.
        """
        for interaction in self.interactions:
            if not interaction.played and stored_key_fn(interaction.request) == live_key:
                interaction.played = True
                return interaction
        return None
