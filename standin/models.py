"""Typed data model shared across layers.

Two families of types keep the layers decoupled:

* ``RawRequest`` / ``RawResponse`` are the *transport-neutral* representation an
  interceptor hands to the engine. They carry raw bytes and never depend on
  httpx (or any other client).
* ``RecordedRequest`` / ``RecordedResponse`` / ``Interaction`` are the
  *on-disk* representation, with bodies encoded into a JSON-friendly shape.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Mode(str, Enum):
    """Record/replay policy for a cassette."""

    ONCE = "once"  # replay if the cassette exists, else record
    NONE = "none"  # replay only; error on any unmatched call (use in CI)
    ALL = "all"  # always re-record, ignoring existing interactions
    NEW_EPISODES = "new_episodes"  # replay matches, record anything new


# -- transport-neutral (in flight) --------------------------------------------
@dataclass
class RawRequest:
    method: str
    url: str
    headers: dict[str, str]
    body: bytes


@dataclass
class RawResponse:
    status_code: int
    headers: dict[str, str]
    body: bytes


# -- persisted (on disk) ------------------------------------------------------
@dataclass
class RecordedRequest:
    method: str
    url: str
    headers: dict[str, str] = field(default_factory=dict)
    body: dict[str, Any] = field(default_factory=dict)


@dataclass
class RecordedResponse:
    status_code: int
    headers: dict[str, str] = field(default_factory=dict)
    body: dict[str, Any] = field(default_factory=dict)


@dataclass
class Interaction:
    request: RecordedRequest
    response: RecordedResponse
    played: bool = False
