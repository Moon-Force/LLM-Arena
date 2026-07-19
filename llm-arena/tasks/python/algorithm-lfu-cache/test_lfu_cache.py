"""Hard correctness tests for LFUCache (LeetCode 460 style)."""

from __future__ import annotations

import pytest

from lfu_cache import LFUCache


class TestLFUBasic:
    def test_example_from_spec(self):
        cache = LFUCache(2)
        cache.put(1, 1)
        cache.put(2, 2)
        assert cache.get(1) == 1
        cache.put(3, 3)
        assert cache.get(2) == -1
        assert cache.get(3) == 3
        cache.put(4, 4)
        assert cache.get(1) == -1
        assert cache.get(3) == 3
        assert cache.get(4) == 4

    def test_capacity_one(self):
        cache = LFUCache(1)
        cache.put(1, 10)
        assert cache.get(1) == 10
        cache.put(2, 20)
        assert cache.get(1) == -1
        assert cache.get(2) == 20

    def test_capacity_zero(self):
        cache = LFUCache(0)
        cache.put(1, 1)
        assert cache.get(1) == -1

    def test_update_existing_increments_freq(self):
        cache = LFUCache(2)
        cache.put(1, 1)
        cache.put(2, 2)
        cache.put(1, 10)  # update: freq(1) becomes 2, value 10
        cache.put(3, 3)  # should evict 2 (freq 1), keep 1
        assert cache.get(1) == 10
        assert cache.get(2) == -1
        assert cache.get(3) == 3

    def test_missing_get(self):
        cache = LFUCache(2)
        assert cache.get(99) == -1


class TestLFUFrequencyTies:
    def test_lru_among_same_freq(self):
        # Both keys freq=1 after insert; access order decides LRU on eviction
        cache = LFUCache(2)
        cache.put(1, 1)
        cache.put(2, 2)
        # neither accessed again; put 3 should evict least-recently-used among freq1 → key 1
        cache.put(3, 3)
        assert cache.get(1) == -1
        assert cache.get(2) == 2
        assert cache.get(3) == 3

    def test_access_protects_from_eviction(self):
        cache = LFUCache(2)
        cache.put(1, 1)
        cache.put(2, 2)
        assert cache.get(2) == 2  # freq(2)=2, freq(1)=1
        cache.put(3, 3)  # evict 1
        assert cache.get(1) == -1
        assert cache.get(2) == 2
        assert cache.get(3) == 3

    def test_multi_level_frequencies(self):
        cache = LFUCache(3)
        for k in (1, 2, 3):
            cache.put(k, k)
        # bump 1 and 2
        assert cache.get(1) == 1
        assert cache.get(1) == 1
        assert cache.get(2) == 2
        # freqs: 1→3, 2→2, 3→1
        cache.put(4, 4)  # evict 3
        assert cache.get(3) == -1
        assert cache.get(1) == 1
        assert cache.get(2) == 2
        assert cache.get(4) == 4


class TestLFUHardSequences:
    def test_leetcode_official_sequence(self):
        # Classic LC 460 example
        c = LFUCache(2)
        c.put(1, 1)
        c.put(2, 2)
        assert c.get(1) == 1
        c.put(3, 3)
        assert c.get(2) == -1
        assert c.get(3) == 3
        c.put(4, 4)
        assert c.get(1) == -1
        assert c.get(3) == 3
        assert c.get(4) == 4

    def test_large_sequence_correctness(self):
        """Long sequence: compare against a slow but correct reference."""
        cap = 50
        cache = LFUCache(cap)
        ref = _SlowLFU(cap)
        ops = []
        # deterministic pseudo-random ops
        x = 1234567
        for i in range(800):
            x = (1103515245 * x + 12345) & 0x7FFFFFFF
            key = (x % 120) + 1
            if x % 3 == 0:
                val = x % 10000
                cache.put(key, val)
                ref.put(key, val)
                ops.append(("put", key, val))
            else:
                assert cache.get(key) == ref.get(key), f"mismatch at op {i}: {ops[-5:]}"

    def test_repeated_put_same_key(self):
        c = LFUCache(1)
        c.put(1, 1)
        c.put(1, 2)
        c.put(1, 3)
        assert c.get(1) == 3
        c.put(2, 9)
        assert c.get(1) == -1
        assert c.get(2) == 9

    def test_evict_then_reinsert(self):
        c = LFUCache(2)
        c.put(1, 1)
        c.put(2, 2)
        c.put(3, 3)
        c.put(1, 10)  # reinsert 1 after eviction
        assert c.get(1) == 10
        assert c.get(2) in (-1, 2)  # 2 may or may not remain depending on order
        # After put(3) keys are {2,3}; put(1) needs eviction of LFU among {2,3}
        # both freq 1, LRU is 2 → {3,1}. So get(2)=-1, get(3)=3
        assert c.get(2) == -1
        assert c.get(3) == 3


class _SlowLFU:
    """Reference LFU for hidden-style checks (not for agents to copy)."""

    def __init__(self, capacity: int) -> None:
        self.cap = capacity
        self.val: dict[int, int] = {}
        self.freq: dict[int, int] = {}
        self.recency: dict[int, int] = {}
        self.clock = 0

    def _touch(self, key: int) -> None:
        self.clock += 1
        self.recency[key] = self.clock
        self.freq[key] = self.freq.get(key, 0) + 1

    def get(self, key: int) -> int:
        if key not in self.val:
            return -1
        self._touch(key)
        return self.val[key]

    def put(self, key: int, value: int) -> None:
        if self.cap <= 0:
            return
        if key in self.val:
            self.val[key] = value
            self._touch(key)
            return
        if len(self.val) >= self.cap:
            # min freq, then min recency
            victim = min(self.val.keys(), key=lambda k: (self.freq[k], self.recency[k]))
            del self.val[victim]
            del self.freq[victim]
            del self.recency[victim]
        self.val[key] = value
        self.freq[key] = 0
        self._touch(key)
