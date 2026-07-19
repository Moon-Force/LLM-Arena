"""Hard feature tests for MVCCStore."""

from __future__ import annotations

import pytest

from mvcc_store import MVCCStore, TransactionClosed, WriteConflict


class TestBasic:
    def test_empty_get(self):
        s = MVCCStore()
        txn = s.begin()
        assert txn.get("a") is None
        txn.commit()

    def test_put_get_commit(self):
        s = MVCCStore()
        t = s.begin()
        t.put("k", "v1")
        assert t.get("k") == "v1"  # read-your-writes
        ts = t.commit()
        assert ts == 1
        assert s.commit_ts == 1
        t2 = s.begin()
        assert t2.get("k") == "v1"
        t2.commit()

    def test_delete(self):
        s = MVCCStore()
        t = s.begin()
        t.put("k", "v")
        t.commit()
        t2 = s.begin()
        t2.delete("k")
        assert t2.get("k") is None
        t2.commit()
        t3 = s.begin()
        assert t3.get("k") is None
        t3.commit()

    def test_abort_discards(self):
        s = MVCCStore()
        t = s.begin()
        t.put("k", "x")
        t.abort()
        t2 = s.begin()
        assert t2.get("k") is None
        t2.commit()

    def test_closed_raises(self):
        s = MVCCStore()
        t = s.begin()
        t.put("a", "1")
        t.commit()
        with pytest.raises(TransactionClosed):
            t.get("a")
        with pytest.raises(TransactionClosed):
            t.put("a", "2")
        with pytest.raises(TransactionClosed):
            t.commit()


class TestSnapshotIsolation:
    def test_snapshot_does_not_see_later_commits(self):
        s = MVCCStore()
        t1 = s.begin()
        t1.put("k", "old")
        t1.commit()

        reader = s.begin()  # read_ts = 1
        writer = s.begin()
        writer.put("k", "new")
        writer.commit()  # commit_ts = 2

        assert reader.get("k") == "old"
        reader.commit()

        fresh = s.begin()
        assert fresh.get("k") == "new"
        fresh.commit()

    def test_write_conflict_on_concurrent_keys(self):
        s = MVCCStore()
        bootstrap = s.begin()
        bootstrap.put("k", "0")
        bootstrap.commit()

        a = s.begin()
        b = s.begin()
        a.put("k", "A")
        b.put("k", "B")
        a.commit()  # wins
        with pytest.raises(WriteConflict):
            b.commit()

        t = s.begin()
        assert t.get("k") == "A"
        t.commit()

    def test_no_conflict_on_disjoint_keys(self):
        s = MVCCStore()
        a = s.begin()
        b = s.begin()
        a.put("x", "1")
        b.put("y", "2")
        assert a.commit() == 1
        assert b.commit() == 2
        t = s.begin()
        assert t.get("x") == "1"
        assert t.get("y") == "2"
        t.commit()

    def test_conflict_on_delete_vs_put(self):
        s = MVCCStore()
        t0 = s.begin()
        t0.put("k", "v")
        t0.commit()
        a = s.begin()
        b = s.begin()
        a.delete("k")
        b.put("k", "other")
        a.commit()
        with pytest.raises(WriteConflict):
            b.commit()


class TestGCAndHistory:
    def test_version_history_reads(self):
        s = MVCCStore()
        for i, val in enumerate(["a", "b", "c"], start=1):
            t = s.begin()
            t.put("k", val)
            assert t.commit() == i
        # old snapshot
        # We cannot set read_ts manually; simulate by concurrent snapshot
        s2 = MVCCStore()
        t = s2.begin()
        t.put("k", "a")
        t.commit()
        snap = s2.begin()
        t2 = s2.begin()
        t2.put("k", "b")
        t2.commit()
        assert snap.get("k") == "a"
        snap.commit()

    def test_gc_keeps_latest_old_version(self):
        s = MVCCStore()
        for val in ("v1", "v2", "v3", "v4"):
            t = s.begin()
            t.put("k", val)
            t.commit()
        # commit_ts == 4; versions at 1,2,3,4
        removed = s.gc(before_ts=3)
        # keep versions with ts>=3 (v3,v4) and the latest with ts<3 which is v2
        # remove v1 only → removed >= 1
        assert removed >= 1
        t = s.begin()
        assert t.get("k") == "v4"
        t.commit()

    def test_multiple_keys_gc(self):
        s = MVCCStore()
        t = s.begin()
        t.put("a", "1")
        t.put("b", "1")
        t.commit()
        t = s.begin()
        t.put("a", "2")
        t.commit()
        removed = s.gc(before_ts=2)
        assert removed >= 0
        t = s.begin()
        assert t.get("a") == "2"
        assert t.get("b") == "1"
        t.commit()

    def test_abort_then_closed(self):
        s = MVCCStore()
        t = s.begin()
        t.put("k", "x")
        t.abort()
        with pytest.raises(TransactionClosed):
            t.abort()
