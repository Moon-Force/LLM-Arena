"""Event dispatcher with retry. BUGS intentionally present."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from event_store import Event, EventStore
from subscription import SubscriptionRegistry


@dataclass
class DeadLetter:
    subscription_id: str
    seq: int
    error: str
    attempts: int


class Dispatcher:
    def __init__(
        self,
        store: EventStore,
        registry: SubscriptionRegistry,
        max_retries: int = 2,
    ) -> None:
        self.store = store
        self.registry = registry
        self.max_retries = max_retries
        self.dead_letters: list[DeadLetter] = []
        # BUG: tracks only subscription_id, not (subscription_id, seq)
        self._delivered: set[str] = set()
        self._last_seq_by_sub: dict[str, int] = {}

    def publish(self, topic: str, payload: Any, meta: dict | None = None) -> Event:
        event = self.store.append(topic, payload, meta)
        self._dispatch_event(event)
        return event

    def replay_from(self, seq_exclusive: int) -> int:
        """Re-dispatch all events with seq > seq_exclusive. Return count attempted."""
        events = self.store.since(seq_exclusive)
        for ev in events:
            self._dispatch_event(ev)
        return len(events)

    def _dispatch_event(self, event: Event) -> None:
        for sub in self.registry.active_subscriptions():
            if not self.registry.matches(sub, event):
                continue
            # BUG: idempotency key is only subscription_id — blocks later events
            if sub.id in self._delivered:
                continue

            # BUG: no ordering check vs last delivered seq
            attempts = 0
            last_err = ""
            # total tries = 1 + max_retries
            while attempts <= self.max_retries:
                attempts += 1
                try:
                    sub.handler(event)
                    self._delivered.add(sub.id)
                    self._last_seq_by_sub[sub.id] = event.seq
                    last_err = ""
                    break
                except Exception as exc:  # noqa: BLE001
                    last_err = str(exc)
            if last_err:
                self.dead_letters.append(
                    DeadLetter(
                        subscription_id=sub.id,
                        seq=event.seq,
                        error=last_err,
                        attempts=attempts,
                    )
                )
