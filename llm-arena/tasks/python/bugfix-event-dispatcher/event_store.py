"""Append-only event log. BUGS intentionally present — fix them."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Event:
    topic: str
    payload: Any
    seq: int = 0
    meta: dict = field(default_factory=dict)


class EventStore:
    """In-memory append-only store with monotonic sequence numbers."""

    def __init__(self) -> None:
        self._events: list[Event] = []
        # BUG: starts at 0 so first seq is 0, but API requires first seq == 1
        self._next_seq = 0

    def append(self, topic: str, payload: Any, meta: Optional[dict] = None) -> Event:
        # BUG: uses post-increment wrong — assigns then increments, but starts at 0
        # Also mutates shared meta default if not careful
        ev = Event(topic=topic, payload=payload, seq=self._next_seq, meta=meta or {})
        self._next_seq += 1
        self._events.append(ev)
        return ev

    def get(self, seq: int) -> Optional[Event]:
        for e in self._events:
            if e.seq == seq:
                return e
        return None

    def since(self, seq_exclusive: int) -> list[Event]:
        """Return events with seq > seq_exclusive, ordered by seq ascending."""
        # BUG: uses >= instead of >, re-includes the boundary event
        return sorted(
            [e for e in self._events if e.seq >= seq_exclusive],
            key=lambda e: e.seq,
        )

    def all(self) -> list[Event]:
        return list(self._events)
