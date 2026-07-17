"""In-memory store for arena runs and fair match snapshots."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class StoredRun:
    id: str
    arena_id: Optional[str]
    model_id: str
    task_id: str
    status: str
    started_at: float
    completed_at: Optional[float] = None
    duration: Optional[float] = None
    tokens_used: Optional[int] = None
    test_results: dict = field(default_factory=dict)
    error: Optional[str] = None
    constraints_fingerprint: str = ""
    provider: str = ""
    version: str = ""


@dataclass
class StoredArena:
    id: str
    task_id: str
    model_ids: list[str]
    status: str
    started_at: float
    constraints: dict
    constraints_fingerprint: str
    run_ids: list[str] = field(default_factory=list)
    completed_at: Optional[float] = None
    parallel: bool = True


class RunStore:
    def __init__(self) -> None:
        self.runs: dict[str, StoredRun] = {}
        self.arenas: dict[str, StoredArena] = {}

    def new_id(self, prefix: str = "run") -> str:
        return f"{prefix}-{uuid.uuid4().hex[:12]}"

    def create_run(
        self,
        *,
        model_id: str,
        task_id: str,
        provider: str,
        version: str,
        constraints_fingerprint: str,
        arena_id: Optional[str] = None,
        status: str = "running",
    ) -> StoredRun:
        run = StoredRun(
            id=self.new_id("run"),
            arena_id=arena_id,
            model_id=model_id,
            task_id=task_id,
            status=status,
            started_at=time.time(),
            constraints_fingerprint=constraints_fingerprint,
            provider=provider,
            version=version,
        )
        self.runs[run.id] = run
        return run

    def finish_run(
        self,
        run_id: str,
        *,
        status: str,
        duration: Optional[float] = None,
        tokens_used: Optional[int] = None,
        test_results: Optional[dict] = None,
        error: Optional[str] = None,
    ) -> Optional[StoredRun]:
        run = self.runs.get(run_id)
        if not run:
            return None
        run.status = status
        run.completed_at = time.time()
        run.duration = duration
        run.tokens_used = tokens_used
        if test_results is not None:
            run.test_results = test_results
        run.error = error
        return run

    def create_arena(
        self,
        *,
        task_id: str,
        model_ids: list[str],
        constraints: dict,
        constraints_fingerprint: str,
        parallel: bool = True,
    ) -> StoredArena:
        arena = StoredArena(
            id=self.new_id("arena"),
            task_id=task_id,
            model_ids=model_ids,
            status="running",
            started_at=time.time(),
            constraints=constraints,
            constraints_fingerprint=constraints_fingerprint,
            parallel=parallel,
        )
        self.arenas[arena.id] = arena
        return arena

    def list_runs(
        self,
        model_id: Optional[str] = None,
        task_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> list[StoredRun]:
        items = list(self.runs.values())
        if model_id:
            items = [r for r in items if r.model_id == model_id]
        if task_id:
            items = [r for r in items if r.task_id == task_id]
        if status:
            items = [r for r in items if r.status == status]
        return sorted(items, key=lambda r: r.started_at, reverse=True)

    def to_public_run(self, run: StoredRun) -> dict[str, Any]:
        return {
            "id": run.id,
            "run_id": run.id,
            "arena_id": run.arena_id,
            "model_id": run.model_id,
            "modelId": run.model_id,
            "task_id": run.task_id,
            "taskId": run.task_id,
            "status": run.status,
            "started_at": run.started_at,
            "startedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(run.started_at)),
            "completed_at": run.completed_at,
            "duration": run.duration,
            "tokens_used": run.tokens_used,
            "tokensUsed": run.tokens_used,
            "test_results": run.test_results,
            "testResults": run.test_results or None,
            "error": run.error,
            "constraints_fingerprint": run.constraints_fingerprint,
            "provider": run.provider,
            "version": run.version,
        }


STORE = RunStore()
