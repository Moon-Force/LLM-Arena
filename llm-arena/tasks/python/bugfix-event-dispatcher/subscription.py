"""Subscription registry with topic patterns. BUGS intentionally present."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

from event_store import Event

FilterFn = Callable[[Event], bool]
HandlerFn = Callable[[Event], None]


@dataclass
class Subscription:
    id: str
    pattern: str
    handler: HandlerFn
    filter_fn: Optional[FilterFn] = None
    active: bool = True


def topic_matches(pattern: str, topic: str) -> bool:
    """Match topic against pattern.

    Rules:
    - Exact match always works.
    - Pattern segments separated by '.'; each segment is either literal or '*'.
    - '*' matches exactly one non-empty segment.
    - Number of segments must be equal.
    """
    # BUG: uses startswith / naive contains, wrong for multi-segment wildcards
    if pattern == topic:
        return True
    if pattern.endswith(".*"):
        prefix = pattern[:-2]
        # BUG: also matches deeper topics like user.profile.updated for user.*
        return topic.startswith(prefix + ".")
    if pattern == "*":
        # BUG: matches multi-segment too
        return True
    return False


class SubscriptionRegistry:
    def __init__(self) -> None:
        self._subs: dict[str, Subscription] = {}
        self._id_counter = 0

    def subscribe(
        self,
        pattern: str,
        handler: HandlerFn,
        filter_fn: Optional[FilterFn] = None,
    ) -> str:
        self._id_counter += 1
        sid = f"sub-{self._id_counter}"
        self._subs[sid] = Subscription(
            id=sid,
            pattern=pattern,
            handler=handler,
            filter_fn=filter_fn,
            active=True,
        )
        return sid

    def unsubscribe(self, subscription_id: str) -> None:
        # BUG: deletes entry but dispatcher may still hold id; should mark inactive
        # Actually delete is ok if dispatcher checks registry — but we only del
        if subscription_id in self._subs:
            del self._subs[subscription_id]

    def get(self, subscription_id: str) -> Optional[Subscription]:
        return self._subs.get(subscription_id)

    def active_subscriptions(self) -> list[Subscription]:
        return [s for s in self._subs.values() if s.active]

    def matches(self, sub: Subscription, event: Event) -> bool:
        if not sub.active:
            return False
        if not topic_matches(sub.pattern, event.topic):
            return False
        if sub.filter_fn is None:
            return True
        # BUG: filter exceptions propagate and crash dispatcher
        return bool(sub.filter_fn(event))
