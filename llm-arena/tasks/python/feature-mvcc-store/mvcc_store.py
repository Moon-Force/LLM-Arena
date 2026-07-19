"""MVCC in-memory key-value store — implement from this stub."""

from __future__ import annotations

from typing import Optional


class WriteConflict(Exception):
    """Raised when commit detects a concurrent write on the same key."""


class TransactionClosed(Exception):
    """Raised when using a committed or aborted transaction."""


class Transaction:
    def __init__(self, store: "MVCCStore", read_ts: int) -> None:
        self._store = store
        self.read_ts = read_ts
        # TODO

    def get(self, key: str) -> Optional[str]:
        raise NotImplementedError

    def put(self, key: str, value: str) -> None:
        raise NotImplementedError

    def delete(self, key: str) -> None:
        raise NotImplementedError

    def commit(self) -> int:
        raise NotImplementedError

    def abort(self) -> None:
        raise NotImplementedError


class MVCCStore:
    def __init__(self) -> None:
        # TODO: version chains per key
        pass

    def begin(self) -> Transaction:
        raise NotImplementedError

    @property
    def commit_ts(self) -> int:
        raise NotImplementedError

    def gc(self, before_ts: int) -> int:
        raise NotImplementedError
