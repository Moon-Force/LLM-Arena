"""Arena runner that orchestrates multi-model comparisons under frozen constraints.

Single-variable principle: only model id / provider / version / api_key / base_url
may differ. Decoding knobs, system prompt, tools, steps, and timeouts are frozen.
"""

from __future__ import annotations

import asyncio
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .agent import AgentResult, AgentStatus, OpenCodeAgent
from .container_runner import ContainerConfig, ContainerRunner
from .fairness import DEFAULT_CONSTRAINTS, FrozenConstraints
from .model_client import ModelClient
from .task_runner import Task, TaskResult, TaskRunner
from .tool_registry import ToolRegistry


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
    """Orchestrates multi-model arena runs with identical frozen constraints."""

    def __init__(
        self,
        task_runner: TaskRunner,
        container_runner: Optional[ContainerRunner] = None,
        constraints: Optional[FrozenConstraints] = None,
    ):
        self.task_runner = task_runner
        self.container_runner = container_runner
        self.constraints = constraints or DEFAULT_CONSTRAINTS
        self._callbacks: list = []

    def on_run_complete(self, callback):
        self._callbacks.append(callback)

    def _docker_ready(self) -> bool:
        return bool(self.container_runner and getattr(self.container_runner, "client", None))

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
    ) -> TaskResult:
        """Run one model on one task under frozen constraints."""
        # Ignore per-model decoding overrides — always use frozen constraints
        steps = self.constraints.max_steps
        to = self.constraints.timeout
        if max_steps is not None:
            steps = min(int(max_steps), self.constraints.max_steps)
        if timeout is not None:
            to = min(int(timeout), self.constraints.timeout)

        if self._docker_ready():
            extra_env: dict = {
                "ARENA_CONSTRAINTS_FP": self.constraints.fingerprint(),
                "SYSTEM_PROMPT_VERSION": self.constraints.system_prompt_version,
                "TEMPERATURE": str(self.constraints.temperature),
                "MAX_TOKENS": str(self.constraints.max_tokens),
            }
            if base_url:
                extra_env["OPENAI_BASE_URL"] = base_url
                extra_env["BASE_URL"] = base_url

            config = ContainerConfig(
                model_id=model_id,
                model_provider=model_provider,
                model_version=model_version,
                api_key=api_key,
                max_steps=steps,
                timeout=to,
                memory_limit=self.constraints.memory_limit,
                cpu_limit=self.constraints.cpu_limit,
                image=self.constraints.container_image,
                environment=extra_env,
            )
            return self.task_runner.run_task_in_container(
                task=task,
                model_config=config,
                container_runner=self.container_runner,
            )

        # Local in-process path (same Agent + tools + frozen prompt)
        return await self._run_local(
            task=task,
            model_id=model_id,
            model_provider=model_provider,
            model_version=model_version,
            api_key=api_key,
            base_url=base_url,
            max_steps=steps,
        )

    async def _run_local(
        self,
        task: Task,
        model_id: str,
        model_provider: str,
        model_version: str,
        api_key: str,
        base_url: Optional[str],
        max_steps: int,
    ) -> TaskResult:
        workspace = Path(tempfile.mkdtemp(prefix=f"opencode_{task.id}_{model_id}_"))
        try:
            self.task_runner.prepare_workspace(task, str(workspace))
            client = ModelClient.create(
                provider=model_provider,
                api_key=api_key,
                model_version=model_version,
                base_url=base_url,
            )
            agent = OpenCodeAgent(
                model_client=client,
                tool_registry=ToolRegistry(),
                max_steps=max_steps,
                constraints=self.constraints,
            )
            agent_result = await agent.run(
                task_description=task.description,
                working_dir=str(workspace),
            )
            test_results = self.task_runner.evaluate_task(task, str(workspace))
            status = (
                "success"
                if agent_result.status == AgentStatus.COMPLETED
                else "failed"
            )
            agent_result.run_id = f"local-{uuid.uuid4().hex[:10]}"
            return TaskResult(
                task_id=task.id,
                model_id=model_id,
                status=status,
                agent_result=agent_result,
                test_results=test_results,
            )
        except Exception as exc:
            return TaskResult(
                task_id=task.id,
                model_id=model_id,
                status="failed",
                agent_result=AgentResult(
                    status=AgentStatus.FAILED,
                    steps=[],
                    error=str(exc),
                    run_id=f"local-{uuid.uuid4().hex[:10]}",
                ),
                test_results={},
            )

    async def run_arena(
        self,
        config: ArenaConfig,
        model_configs: dict[str, dict],  # model_id -> {provider, version, api_key, base_url?}
    ) -> ArenaResult:
        """Run the same task across models with identical frozen constraints."""
        result = ArenaResult(
            config=config,
            constraints_fingerprint=self.constraints.fingerprint(),
            constraints=self.constraints.to_public_dict(),
            arena_id=f"arena-{uuid.uuid4().hex[:12]}",
        )
        result.start_time = time.time()

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
                    "duration": getattr(tr.agent_result, "total_duration", 0) or 0,
                    "pass_rate": (passed / total * 100) if total else None,
                    "test_results": tests,
                    "error": getattr(tr.agent_result, "error", None),
                }
            )
        return {
            "arena_id": result.arena_id,
            "task_id": result.config.task_id,
            "constraints_fingerprint": result.constraints_fingerprint,
            "duration": result.duration,
            "entries": entries,
        }
