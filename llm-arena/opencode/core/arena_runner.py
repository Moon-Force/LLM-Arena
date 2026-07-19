"""Arena runner: multi-model fair matches via official OpenCode (opencode-ai).

Single-variable principle: only model id / provider / version / api_key / base_url
may differ. Decoding knobs, system prompt, tools, steps, and timeouts are frozen.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .agent import AgentResult, AgentStatus
from .fairness import DEFAULT_CONSTRAINTS, FrozenConstraints
from .task_runner import Task, TaskResult, TaskRunner


@dataclass
class ArenaConfig:
    """Configuration for an arena run (shared control variables)."""
    task_id: str
    model_ids: list[str]
    max_steps: int = DEFAULT_CONSTRAINTS.max_steps
    timeout: int = DEFAULT_CONSTRAINTS.timeout
    repetitions: int = 1
    parallel: bool = True


@dataclass
class ArenaResult:
    """Result of an arena comparison."""
    config: ArenaConfig
    results: list[TaskResult] = field(default_factory=list)
    start_time: float = 0.0
    end_time: float = 0.0
    constraints_fingerprint: str = ""
    constraints: dict = field(default_factory=dict)
    arena_id: str = ""

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time


class ArenaRunner:
    """Orchestrates multi-model arena runs with official OpenCode as the agent."""

    def __init__(
        self,
        task_runner: TaskRunner,
        constraints: Optional[FrozenConstraints] = None,
    ):
        self.task_runner = task_runner
        self.constraints = constraints or DEFAULT_CONSTRAINTS
        self._callbacks: list = []

    def on_run_complete(self, callback):
        self._callbacks.append(callback)

    async def run_single(
        self,
        task: Task,
        model_id: str,
        model_provider: str,
        model_version: str,
        api_key: str,
        max_steps: Optional[int] = None,
        timeout: Optional[int] = None,
        base_url: Optional[str] = None,
        store_run_id: Optional[str] = None,
    ) -> TaskResult:
        """Run one model on one task under frozen constraints (official OpenCode)."""
        steps = self.constraints.max_steps
        to = self.constraints.timeout
        if max_steps is not None:
            steps = min(int(max_steps), self.constraints.max_steps)
        if timeout is not None:
            to = min(int(timeout), self.constraints.timeout)

        from .workspace import DEFAULT_WORKSPACE_MANAGER

        agent_ws = DEFAULT_WORKSPACE_MANAGER.create(
            model_id=model_id,
            task_id=task.id,
            run_id=uuid.uuid4().hex[:12],
        )
        ws_src = str(agent_ws.src_dir)

        # Seed UI immediately
        if store_run_id:
            try:
                from .run_store import STORE
                from .task_prompt import build_task_prompt
                from .agent_serialize import steps_to_messages

                prompt = build_task_prompt(task)
                seed_msgs = steps_to_messages(
                    [],
                    task_prompt=prompt,
                    model_id=model_id,
                    status="running",
                )
                seed_msgs.append(
                    {
                        "id": "msg_sys_start",
                        "type": "system",
                        "role": "system",
                        "text": (
                            "Official OpenCode agent starting… "
                            "(Docker hard isolation when available — only this workspace is mounted)"
                        ),
                    }
                )
                STORE.update_run(
                    store_run_id,
                    workspace_path=ws_src,
                    status="running",
                    agent_messages=seed_msgs,
                    agent_log="[OpenCode official] starting (isolation=auto/docker)…",
                )
            except Exception:
                pass

        return await self._run_official(
            task=task,
            model_id=model_id,
            model_provider=model_provider,
            model_version=model_version,
            api_key=api_key,
            base_url=base_url,
            max_steps=steps,
            timeout=to,
            workspace_src=ws_src,
            run_id=agent_ws.run_id,
            store_run_id=store_run_id,
        )

    async def _run_official(
        self,
        task: Task,
        model_id: str,
        model_provider: str,
        model_version: str,
        api_key: str,
        base_url: Optional[str],
        max_steps: int,
        timeout: int,
        workspace_src: Optional[str] = None,
        run_id: Optional[str] = None,
        store_run_id: Optional[str] = None,
    ) -> TaskResult:
        """Run one contestant with the official opencode-ai binary (serve + HTTP)."""
        from .opencode_runtime import run_with_official_opencode
        from .task_prompt import build_task_prompt
        from .workspace import DEFAULT_WORKSPACE_MANAGER

        if workspace_src:
            workspace = Path(workspace_src)
            workspace.mkdir(parents=True, exist_ok=True)
        else:
            agent_ws = DEFAULT_WORKSPACE_MANAGER.create(
                model_id=model_id,
                task_id=task.id,
                run_id=run_id,
            )
            workspace = agent_ws.src_dir
            run_id = agent_ws.run_id

        try:
            self.task_runner.prepare_workspace(task, str(workspace))
            task_prompt = build_task_prompt(task)

            official = await asyncio.to_thread(
                run_with_official_opencode,
                workspace=workspace,
                task_prompt=task_prompt,
                model_id=model_id,
                provider=model_provider,
                model_version=model_version,
                api_key=api_key,
                base_url=base_url,
                temperature=self.constraints.temperature,
                max_steps=max_steps,
                timeout=timeout,
                system_prompt=self.constraints.system_prompt,
                store_run_id=store_run_id,
            )

            test_results = self.task_runner.evaluate_task(task, str(workspace))
            agent_result = official.agent_result
            agent_result.run_id = run_id or official.session_id or f"oc-{uuid.uuid4().hex[:10]}"
            status = "success" if official.status == "success" else "failed"

            return TaskResult(
                task_id=task.id,
                model_id=model_id,
                status=status,
                agent_result=agent_result,
                test_results=test_results,
                workspace_path=str(workspace),
            )
        except Exception as exc:
            if store_run_id:
                try:
                    from .run_store import STORE

                    STORE.update_run(store_run_id, status="failed", error=str(exc))
                except Exception:
                    pass
            return TaskResult(
                task_id=task.id,
                model_id=model_id,
                status="failed",
                agent_result=AgentResult(
                    status=AgentStatus.FAILED,
                    steps=[],
                    error=str(exc),
                    run_id=run_id or f"oc-{uuid.uuid4().hex[:10]}",
                ),
                test_results={},
                workspace_path=str(workspace) if workspace else "",
            )

    async def run_arena(
        self,
        config: ArenaConfig,
        model_configs: dict[str, dict],
        store_run_ids: Optional[dict[str, str]] = None,
    ) -> ArenaResult:
        """Run the same task across models with identical frozen constraints."""
        result = ArenaResult(
            config=config,
            constraints_fingerprint=self.constraints.fingerprint(),
            constraints=self.constraints.to_public_dict(),
            arena_id=f"arena-{uuid.uuid4().hex[:12]}",
        )
        result.start_time = time.time()
        store_run_ids = store_run_ids or {}

        task = self.task_runner.get_task(config.task_id)
        if not task:
            raise ValueError(f"Task not found: {config.task_id}")

        async def _one(model_id: str) -> TaskResult:
            mc = model_configs.get(model_id, {})
            if not mc:
                raise ValueError(f"Missing model config for {model_id}")
            return await self.run_single(
                task=task,
                model_id=model_id,
                model_provider=mc["provider"],
                model_version=mc["version"],
                api_key=mc["api_key"],
                max_steps=self.constraints.max_steps,
                timeout=self.constraints.timeout,
                base_url=mc.get("base_url"),
                store_run_id=store_run_ids.get(model_id),
            )

        if config.parallel:
            gathered = await asyncio.gather(
                *[_one(mid) for mid in config.model_ids if mid in model_configs],
                return_exceptions=True,
            )
            for r in gathered:
                if isinstance(r, Exception):
                    print(f"Task failed: {r}")
                    continue
                result.results.append(r)
        else:
            for model_id in config.model_ids:
                if model_id not in model_configs:
                    continue
                result.results.append(await _one(model_id))

        result.end_time = time.time()
        for callback in self._callbacks:
            callback(result)
        return result

    def generate_report(self, result: ArenaResult) -> dict[str, Any]:
        """Generate a comparison report from arena results (no simulated metrics)."""
        entries = []
        for tr in result.results:
            tests = tr.test_results or {}
            total = tests.get("total") or tests.get("test_cases") or 0
            passed = tests.get("passed", 0)
            entries.append(
                {
                    "model_id": tr.model_id,
                    "status": tr.status,
                    "tokens": getattr(tr.agent_result, "total_tokens", 0) or 0,
                    "input_tokens": getattr(tr.agent_result, "input_tokens", 0) or 0,
                    "output_tokens": getattr(tr.agent_result, "output_tokens", 0) or 0,
                    "duration": getattr(tr.agent_result, "total_duration", 0) or 0,
                    "pass_rate": (passed / total * 100) if total else None,
                    "test_results": tests,
                    "error": getattr(tr.agent_result, "error", None),
                    "workspace_path": tr.workspace_path,
                }
            )
        return {
            "arena_id": result.arena_id,
            "task_id": result.config.task_id,
            "constraints_fingerprint": result.constraints_fingerprint,
            "duration": result.duration,
            "entries": entries,
        }
