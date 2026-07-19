"""Hard multi-file tests for the event dispatcher system."""

from __future__ import annotations

import pytest

from dispatcher import Dispatcher
from event_store import EventStore
from subscription import SubscriptionRegistry, topic_matches


class TestTopicMatch:
    def test_exact(self):
        assert topic_matches("user.created", "user.created")
        assert not topic_matches("user.created", "user.deleted")

    def test_single_wildcard_segment(self):
        assert topic_matches("user.*", "user.created")
        assert topic_matches("user.*", "user.deleted")
        assert not topic_matches("user.*", "user.profile.updated")
        assert not topic_matches("user.*", "order.created")

    def test_star_alone(self):
        assert topic_matches("*", "created")
        assert not topic_matches("*", "user.created")

    def test_multi_wildcard(self):
        assert topic_matches("a.*.c", "a.b.c")
        assert not topic_matches("a.*.c", "a.b.d")
        assert not topic_matches("a.*.c", "a.b.c.d")


class TestEventStore:
    def test_seq_starts_at_one(self):
        store = EventStore()
        e1 = store.append("t", 1)
        e2 = store.append("t", 2)
        assert e1.seq == 1
        assert e2.seq == 2

    def test_since_exclusive(self):
        store = EventStore()
        store.append("t", "a")
        store.append("t", "b")
        store.append("t", "c")
        got = store.since(1)
        assert [e.payload for e in got] == ["b", "c"]


class TestDispatcherCore:
    def test_basic_delivery(self):
        store = EventStore()
        reg = SubscriptionRegistry()
        disp = Dispatcher(store, reg)
        received = []

        reg.subscribe("order.created", lambda e: received.append(e.payload))
        disp.publish("order.created", {"id": 1})
        assert received == [{"id": 1}]

    def test_ordering_per_subscriber(self):
        store = EventStore()
        reg = SubscriptionRegistry()
        disp = Dispatcher(store, reg)
        seqs = []

        reg.subscribe("ev", lambda e: seqs.append(e.seq))
        for i in range(5):
            disp.publish("ev", i)
        assert seqs == [1, 2, 3, 4, 5]

    def test_wildcard_delivery(self):
        store = EventStore()
        reg = SubscriptionRegistry()
        disp = Dispatcher(store, reg)
        got = []
        reg.subscribe("user.*", lambda e: got.append(e.topic))
        disp.publish("user.created", 1)
        disp.publish("user.profile.updated", 2)  # must NOT match user.*
        disp.publish("user.deleted", 3)
        assert got == ["user.created", "user.deleted"]

    def test_filter_predicate(self):
        store = EventStore()
        reg = SubscriptionRegistry()
        disp = Dispatcher(store, reg)
        got = []
        reg.subscribe(
            "n",
            lambda e: got.append(e.payload),
            filter_fn=lambda e: e.payload % 2 == 0,
        )
        for i in range(5):
            disp.publish("n", i)
        assert got == [0, 2, 4]

    def test_filter_exception_skipped(self):
        store = EventStore()
        reg = SubscriptionRegistry()
        disp = Dispatcher(store, reg)
        got = []

        def bad_filter(e):
            if e.payload == 1:
                raise RuntimeError("boom")
            return True

        reg.subscribe("n", lambda e: got.append(e.payload), filter_fn=bad_filter)
        disp.publish("n", 0)
        disp.publish("n", 1)
        disp.publish("n", 2)
        assert got == [0, 2]
        assert disp.dead_letters == []

    def test_unsubscribe(self):
        store = EventStore()
        reg = SubscriptionRegistry()
        disp = Dispatcher(store, reg)
        got = []
        sid = reg.subscribe("t", lambda e: got.append(e.payload))
        disp.publish("t", 1)
        reg.unsubscribe(sid)
        disp.publish("t", 2)
        assert got == [1]

    def test_retry_then_success(self):
        store = EventStore()
        reg = SubscriptionRegistry()
        disp = Dispatcher(store, reg, max_retries=2)
        state = {"n": 0}
        got = []

        def flaky(e):
            state["n"] += 1
            if state["n"] < 3:
                raise RuntimeError("fail")
            got.append(e.payload)

        reg.subscribe("t", flaky)
        disp.publish("t", "ok")
        assert got == ["ok"]
        assert disp.dead_letters == []

    def test_retry_exhausted_dead_letter(self):
        store = EventStore()
        reg = SubscriptionRegistry()
        disp = Dispatcher(store, reg, max_retries=2)

        def always_fail(e):
            raise ValueError("nope")

        reg.subscribe("t", always_fail)
        ev = disp.publish("t", 1)
        assert len(disp.dead_letters) == 1
        assert disp.dead_letters[0].seq == ev.seq
        assert disp.dead_letters[0].attempts == 3

    def test_idempotent_republish(self):
        store = EventStore()
        reg = SubscriptionRegistry()
        disp = Dispatcher(store, reg)
        got = []
        reg.subscribe("t", lambda e: got.append(e.seq))
        ev = disp.publish("t", "a")
        # re-dispatch same event should not double-deliver
        disp._dispatch_event(ev)
        assert got == [ev.seq]

    def test_replay_does_not_duplicate(self):
        store = EventStore()
        reg = SubscriptionRegistry()
        disp = Dispatcher(store, reg)
        got = []
        reg.subscribe("t", lambda e: got.append(e.payload))
        disp.publish("t", 1)
        disp.publish("t", 2)
        disp.replay_from(0)
        assert got == [1, 2]

    def test_multiple_subscribers_independent(self):
        store = EventStore()
        reg = SubscriptionRegistry()
        disp = Dispatcher(store, reg)
        a, b = [], []
        reg.subscribe("t", lambda e: a.append(e.payload))
        reg.subscribe("t", lambda e: b.append(e.payload))
        disp.publish("t", 9)
        assert a == [9] and b == [9]
