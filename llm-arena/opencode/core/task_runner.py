"""Task runner for executing coding tasks.

Manages task definitions, prepares workspaces, and runs tasks
through the agent system.
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .agent import OpenCodeAgent, AgentResult
from .container_runner import ContainerConfig, ContainerRunner


@dataclass
class Task:
    """Definition of a coding task."""
    id: str
    name: str
    description: str
    language: str  # "python", "typescript", etc.
    type: str  # "bugfix", "feature"
    difficulty: str  # "easy", "medium", "hard"
    test_cases: int = 0
    source_path: str = ""  # Path to task files
    expected_files: list[str] = field(default_factory=list)
    hidden_tests: list[dict] = field(default_factory=list)


@dataclass
class TaskResult:
    """Result of running a task."""
    task_id: str
    model_id: str
    status: str
    agent_result: AgentResult
    test_results: dict = field(default_factory=dict)
    code_diff: str = ""
    tool_calls: list = field(default_factory=list)


class TaskRunner:
    """Manages task execution.

    Each task run:
    1. Prepares a clean workspace
    2. Copies task files
    3. Runs the agent
    4. Evaluates results
    5. Cleans up
    """

    def __init__(self, tasks_dir: str = "tasks"):
        self.tasks_dir = Path(tasks_dir)
        self.tasks: dict[str, Task] = {}
        self._load_tasks()

    def _load_tasks(self) -> None:
        """Load all available tasks from the tasks directory."""
        if not self.tasks_dir.exists():
            return

        for task_file in self.tasks_dir.rglob("task.json"):
            with open(task_file, "r") as f:
                task_data = json.load(f)
                task = Task(
                    id=task_data["id"],
                    name=task_data["name"],
                    description=task_data["description"],
                    language=task_data["language"],
                    type=task_data["type"],
                    difficulty=task_data["difficulty"],
                    test_cases=task_data.get("test_cases", 0),
                    source_path=str(task_file.parent),
                    expected_files=task_data.get("expected_files", []),
                    hidden_tests=task_data.get("hidden_tests", []),
                )
                self.tasks[task.id] = task

    def get_task(self, task_id: str) -> Optional[Task]:
        """Get a task by ID."""
        return self.tasks.get(task_id)

    def list_tasks(self, language: Optional[str] = None, difficulty: Optional[str] = None) -> list[Task]:
        """List tasks with optional filtering."""
        tasks = list(self.tasks.values())

        if language:
            tasks = [t for t in tasks if t.language == language]
        if difficulty:
            tasks = [t for t in tasks if t.difficulty == difficulty]

        return tasks

    def prepare_workspace(self, task: Task, workspace_path: str) -> None:
        """Prepare a workspace for a task.

        Args:
            task: Task to prepare
            workspace_path: Path to the workspace directory
        """
        workspace = Path(workspace_path)
        workspace.mkdir(parents=True, exist_ok=True)

        # Copy task files to workspace
        if task.source_path:
            source = Path(task.source_path)
            if source.exists():
                for item in source.iterdir():
                    if item.name == "task.json":
                        continue  # Skip metadata

                    dest = workspace / item.name
                    if item.is_dir():
                        shutil.copytree(item, dest, dirs_exist_ok=True)
                    else:
                        shutil.copy2(item, dest)

    def evaluate_task(self, task: Task, workspace_path: str) -> dict:
        """Evaluate a completed task.

        Args:
            task: Task definition
            workspace_path: Path to the workspace

        Returns:
            Evaluation results
        """
        results = {
            "task_id": task.id,
            "passed": 0,
            "failed": 0,
            "total": 0,
            "details": [],
        }

        # Run tests
        test_path = Path(workspace_path) / "tests"
        if test_path.exists():
            import subprocess

            try:
                result = subprocess.run(
                    f"python -m pytest {test_path} -v --tb=short",
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=60,
                    cwd=workspace_path,
                )

                # Parse results
                import re
                passed = len(re.findall(r'PASSED', result.stdout))
                failed = len(re.findall(r'FAILED', result.stdout))

                results["passed"] = passed
                results["failed"] = failed
                results["total"] = passed + failed
                results["stdout"] = result.stdout
                results["stderr"] = result.stderr

            except Exception as e:
                results["error"] = str(e)

        # Check expected files
        for expected_file in task.expected_files:
            file_path = Path(workspace_path) / expected_file
            results["details"].append({
                "file": expected_file,
                "exists": file_path.exists(),
                "size": file_path.stat().st_size if file_path.exists() else 0,
            })

        return results

    def run_task_in_container(
        self,
        task: Task,
        model_config: ContainerConfig,
        container_runner: ContainerRunner,
    ) -> TaskResult:
        """Run a task in a Docker container.

        Args:
            task: Task to run
            model_config: Model configuration
            container_runner: Container runner instance

        Returns:
            TaskResult with execution details
        """
        # Prepare workspace
        workspace_path = f"/tmp/opencode_{task.id}_{model_config.model_id}"
        self.prepare_workspace(task, workspace_path)

        # Run in container
        result = container_runner.run_task(
            config=model_config,
            task_path=task.source_path,
        )

        # Evaluate results
        test_results = self.evaluate_task(task, workspace_path)

        return TaskResult(
            task_id=task.id,
            model_id=model_config.model_id,
            status=result.status,
            agent_result=AgentResult(
                status="completed" if result.status == "success" else "failed",
                steps=[],
                total_duration=result.duration,
            ),
            test_results=test_results,
            code_diff=result.stdout,
        )
