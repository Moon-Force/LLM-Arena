"""LFU Cache — implement get/put with correct frequency + LRU-within-frequency eviction.

This starter intentionally does nothing useful. Pass all tests in test_lfu_cache.py.
"""

from __future__ import annotations


class LFUCache:
    """Least Frequently Used cache.

    Eviction: lowest frequency first; on ties, least recently used among that frequency.
    """

    def __init__(self, capacity: int) -> None:
        self.capacity = capacity
        # TODO: implement internal structures

    def get(self, key: int) -> int:
        """Return value for key, or -1. Successful get increases frequency."""
        raise NotImplementedError("Implement LFUCache.get")

    def put(self, key: int, value: int) -> None:
        """Insert or update key. Evict LFU (then LRU) when over capacity."""
        raise NotImplementedError("Implement LFUCache.put")
