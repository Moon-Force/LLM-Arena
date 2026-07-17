"""Arena runner that orchestrates multi-model comparisons.

Manages running the same task across multiple models and
collecting results for comparison.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Optional

from .agent import AgentStatus
from .container_runner import ContainerConfig, ContainerRunner
from .task_runner import Task, TaskRunner, TaskResult


@dataclass
class ArenaConfig:
    """Configuration for an arena run."""
    task_id: str
    model_ids: list[str]
    max_steps: int = 100
    timeout: int = 300
    repetitions: int = 3
    parallel: bool = True


@dataclass
class ArenaResult:
    """Result of an arena comparison."""
    config: ArenaConfig
    results: list[TaskResult] = field(default_factory=list)
    start_time: float = 0.0
    end_time: float = 0.0

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time


class ArenaRunner:
    """Orchestrates multi-model arena runs.

    Runs the same task across multiple models with identical
    configurations to ensure fair comparison.
    """

    def __init__(self, task_runner: TaskRunner, container_runner: ContainerRunner):
        self.task_runner = task_runner
        self.container_runner = container_runner
        self._callbacks: list = []

    def on_run_complete(self, callback):
        """Register callback for run completion."""
        self._callbacks.append(callback)

    async def run_single(
        self,
        task: Task,
        model_id: str,
        model_provider: str,
        model_version: str,
        api_key: str,
        max_steps: int = 100,
        timeout: int = 300,
        base_url: Optional[str] = None,
    ) -> TaskResult:
        """Run a single task with a single model.

        Args:
            task: Task to run
            model_id: Model identifier
            model_provider: Model provider (anthropic, openai, etc.)
            model_version: Model version string
            api_key: API key for the model (from frontend or env)
            max_steps: Maximum agent steps
            timeout: Timeout in seconds
            base_url: Optional custom API base URL

        Returns:
            TaskResult with execution details
        """
        extra_env: dict = {}
        if base_url:
            extra_env["OPENAI_BASE_URL"] = base_url
            extra_env["BASE_URL"] = base_url

        config = ContainerConfig(
            model_id=model_id,
            model_provider=model_provider,
            model_version=model_version,
            api_key=api_key,
            max_steps=max_steps,
            timeout=timeout,
            environment=extra_env,
        )

        return self.task_runner.run_task_in_container(
            task=task,
            model_config=config,
            container_runner=self.container_runner,
        )

    async def run_arena(
        self,
        config: ArenaConfig,
        model_configs: dict[str, dict],  # model_id -> {provider, version, api_key}
    ) -> ArenaResult:
        """Run an arena comparison across multiple models.

        Args:
            config: Arena configuration
            model_configs: Map of model_id to configuration

        Returns:
            ArenaResult with all model results
        """
        result = ArenaResult(config=config)
        result.start_time = time.time()

        task = self.task_runner.get_task(config.task_id)
        if not task:
            raise ValueError(f"Task not found: {config.task_id}")

        if config.parallel:
            # Run all models in parallel
            tasks = []
            for model_id in config.model_ids:
                model_config = model_configs.get(model_id, {})
                if not model_config:
                    continue

                t = self.run_single(
                    task=task,
                    model_id=model_id,
                    model_provider=model_config["provider"],
                    model_version=model_config["version"],
                    api_key=model_config["api_key"],
                    max_steps=config.max_steps,
                    timeout=config.timeout,
                )
                tasks.append(t)

            # Wait for all to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for r in results:
                if isinstance(r, Exception):
                    print(f"Task failed: {r}")
                    continue
                result.results.append(r)

        else:
            # Run sequentially
            for model_id in config.model_ids:
                model_config = model_configs.get(model_id, {})
                if not model_config:
                    continue

                r = await self.run_single(
                    task=task,
                    model_id=model_id,
                    model_provider=model_config["provider"],
                    model_version=model_config["version"],
                    api_key=model_config["api_key"],
                    max_steps=config.max_steps,
                    timeout=config.timeout,
                )
                result.results.append(r)

        result.end_time = time.time()

        # Notify callbacks
        for callback in self._callbacks:
            callback(result)

        return result

    def generate_report(self, result: ArenaResult) -> dict:
        """Generate a comparison report from arena results.

        Args:
            result: ArenaResult from run_arena

        Returns:
            Report dict with comparisons
        """
        report = {
            "task_id": result.config.task_id,
            "duration": result.duration,
            "models": {},
        }

        for task_result in result.results:
            model_id = task_result.model_id
            report["models"][model_id] = {
                "status": task_result.status,
                "test_passed": task_result.test_results.get("passed", 0),
                "test_failed": task_result.test_results.get("failed", 0),
                "test_total": task_result.test_results.get("total", 0),
                "duration": task_result.agent_result.total_duration,
                "tokens": task_result.agent_result.total_tokens,
            }

        return report
