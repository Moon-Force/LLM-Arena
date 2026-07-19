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
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    test_results: dict = field(default_factory=dict)
    error: Optional[str] = None
    constraints_fingerprint: str = ""
    provider: str = ""
    version: str = ""
    workspace_path: str = ""
    # Evaluation track (same for all models in a fair match)
    track: str = ""
    # OpenCode agent transcript (steps / tool calls / observations)
    agent_steps: list = field(default_factory=list)
    # OpenCode-style conversation messages (user / assistant / system + parts)
    agent_messages: list = field(default_factory=list)
    agent_log: str = ""


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
    track: str = ""


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
        track: str = "",
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
            track=track or "",
        )
        self.runs[run.id] = run
        return run

    def update_run(
        self,
        run_id: str,
        *,
        status: Optional[str] = None,
        duration: Optional[float] = None,
        tokens_used: Optional[int] = None,
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
        test_results: Optional[dict] = None,
        error: Optional[str] = None,
        workspace_path: Optional[str] = None,
        agent_steps: Optional[list] = None,
        agent_messages: Optional[list] = None,
        agent_log: Optional[str] = None,
    ) -> Optional[StoredRun]:
        """Partial update while a run is still in progress (live steps)."""
        run = self.runs.get(run_id)
        if not run:
            return None
        if status is not None:
            run.status = status
        if duration is not None:
            run.duration = duration
        if tokens_used is not None:
            run.tokens_used = tokens_used
        if input_tokens is not None:
            run.input_tokens = input_tokens
        if output_tokens is not None:
            run.output_tokens = output_tokens
        if test_results is not None:
            run.test_results = test_results
        if error is not None:
            run.error = error
        if workspace_path is not None:
            run.workspace_path = workspace_path
        if agent_steps is not None:
            run.agent_steps = agent_steps
            # Keep conversation timeline in sync with steps when messages not provided
            if agent_messages is None and agent_steps:
                try:
                    from .agent_serialize import steps_to_messages

                    run.agent_messages = steps_to_messages(
                        agent_steps,
                        model_id=run.model_id,
                        status=run.status,
                        error=run.error,
                    )
                except Exception:
                    pass
        if agent_messages is not None:
            run.agent_messages = agent_messages
        if agent_log is not None:
            run.agent_log = agent_log
        return run

    def finish_run(
        self,
        run_id: str,
        *,
        status: str,
        duration: Optional[float] = None,
        tokens_used: Optional[int] = None,
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
        test_results: Optional[dict] = None,
        error: Optional[str] = None,
        workspace_path: Optional[str] = None,
        agent_steps: Optional[list] = None,
        agent_messages: Optional[list] = None,
        agent_log: Optional[str] = None,
    ) -> Optional[StoredRun]:
        run = self.update_run(
            run_id,
            status=status,
            duration=duration,
            tokens_used=tokens_used,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            test_results=test_results,
            error=error,
            workspace_path=workspace_path,
            agent_steps=agent_steps,
            agent_messages=agent_messages,
            agent_log=agent_log,
        )
        if not run:
            return None
        run.completed_at = time.time()
        return run

    def create_arena(
        self,
        *,
        task_id: str,
        model_ids: list[str],
        constraints: dict,
        constraints_fingerprint: str,
        parallel: bool = True,
        track: str = "",
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
            track=track or "",
        )
        self.arenas[arena.id] = arena
        return arena

    def list_runs(
        self,
        model_id: Optional[str] = None,
        task_id: Optional[str] = None,
        status: Optional[str] = None,
        track: Optional[str] = None,
    ) -> list[StoredRun]:
        items = list(self.runs.values())
        if model_id:
            items = [r for r in items if r.model_id == model_id]
        if task_id:
            items = [r for r in items if r.task_id == task_id]
        if status:
            items = [r for r in items if r.status == status]
        if track and track.lower() != "all":
            t = track.lower().strip()
            items = [r for r in items if (r.track or "") == t]
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
            "track": run.track or "",
            "trackId": run.track or "",
            "status": run.status,
            "started_at": run.started_at,
            "startedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(run.started_at)),
            "completed_at": run.completed_at,
            "duration": run.duration,
            "tokens_used": run.tokens_used,
            "tokensUsed": run.tokens_used,
            "input_tokens": run.input_tokens,
            "inputTokens": run.input_tokens,
            "output_tokens": run.output_tokens,
            "outputTokens": run.output_tokens,
            "test_results": run.test_results,
            "testResults": run.test_results or None,
            "error": run.error,
            "constraints_fingerprint": run.constraints_fingerprint,
            "provider": run.provider,
            "version": run.version,
            "workspace_path": run.workspace_path,
            "workspacePath": run.workspace_path,
            "agent_steps": run.agent_steps,
            "agentSteps": run.agent_steps,
            "agent_messages": run.agent_messages,
            "agentMessages": run.agent_messages,
            "agent_log": run.agent_log,
            "agentLog": run.agent_log,
        }


STORE = RunStore()
