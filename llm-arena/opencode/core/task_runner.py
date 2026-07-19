"""Task runner: load tasks, prepare workspaces, evaluate with pytest."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .agent import AgentResult
from .tracks import infer_track


@dataclass
class Task:
    """Definition of a coding task."""
    id: str
    name: str
    description: str
    language: str
    type: str
    difficulty: str
    test_cases: int = 0
    source_path: str = ""
    expected_files: list[str] = field(default_factory=list)
    hidden_tests: list[dict] = field(default_factory=list)
    # Evaluation track (task pool partition only — not a free variable per model)
    track: str = "feature"


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
    workspace_path: str = ""


class TaskRunner:
    """Manages task definitions, workspace seeding, and evaluation."""

    def __init__(self, tasks_dir: str = "tasks"):
        self.tasks_dir = Path(tasks_dir)
        self.tasks: dict[str, Task] = {}
        self._load_tasks()

    def _load_tasks(self) -> None:
        if not self.tasks_dir.exists():
            return

        for task_file in self.tasks_dir.rglob("task.json"):
            with open(task_file, "r", encoding="utf-8") as f:
                task_data = json.load(f)
                lang = task_data.get("language", "")
                typ = task_data.get("type", "")
                track = infer_track(lang, typ, task_data.get("track"))
                task = Task(
                    id=task_data["id"],
                    name=task_data["name"],
                    description=task_data["description"],
                    language=lang,
                    type=typ,
                    difficulty=task_data["difficulty"],
                    test_cases=task_data.get("test_cases", 0),
                    source_path=str(task_file.parent),
                    expected_files=task_data.get("expected_files", []),
                    hidden_tests=task_data.get("hidden_tests", []),
                    track=track,
                )
                self.tasks[task.id] = task

    def get_task(self, task_id: str) -> Optional[Task]:
        return self.tasks.get(task_id)

    def list_tasks(
        self,
        language: Optional[str] = None,
        difficulty: Optional[str] = None,
        track: Optional[str] = None,
    ) -> list[Task]:
        tasks = list(self.tasks.values())
        if language:
            tasks = [t for t in tasks if t.language == language]
        if difficulty:
            tasks = [t for t in tasks if t.difficulty == difficulty]
        if track and track.lower() != "all":
            t = track.lower().strip()
            tasks = [x for x in tasks if x.track == t]
        return tasks

    def count_by_track(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for t in self.tasks.values():
            counts[t.track] = counts.get(t.track, 0) + 1
        return counts

    def prepare_workspace(self, task: Task, workspace_path: str) -> None:
        workspace = Path(workspace_path)
        workspace.mkdir(parents=True, exist_ok=True)

        if not task.source_path:
            return
        source = Path(task.source_path)
        if not source.exists():
            return

        for item in source.iterdir():
            if item.name == "task.json":
                dest = workspace / "TASK_BRIEF.md"
                try:
                    data = json.loads(item.read_text(encoding="utf-8"))
                    dest.write_text(
                        f"# {data.get('name', task.name)}\n\n"
                        f"{data.get('description', task.description)}\n\n"
                        f"Expected files: {data.get('expected_files', task.expected_files)}\n"
                        f"Run: python -m pytest -v --tb=short\n",
                        encoding="utf-8",
                    )
                except Exception:
                    pass
                continue

            dest = workspace / item.name
            if item.is_dir():
                shutil.copytree(item, dest, dirs_exist_ok=True)
            else:
                shutil.copy2(item, dest)

    def evaluate_task(self, task: Task, workspace_path: str) -> dict:
        results = {
            "task_id": task.id,
            "passed": 0,
            "failed": 0,
            "total": 0,
            "details": [],
        }

        import re
        import subprocess

        workspace = Path(workspace_path)
        test_path = workspace / "tests"
        if test_path.exists():
            pytest_target = str(test_path)
        else:
            root_tests = list(workspace.glob("test_*.py")) + list(workspace.glob("*_test.py"))
            pytest_target = " ".join(str(p) for p in root_tests) if root_tests else ""

        if pytest_target:
            try:
                result = subprocess.run(
                    f"python -m pytest {pytest_target} -v --tb=short",
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=60,
                    cwd=workspace_path,
                )
                passed = len(re.findall(r"PASSED", result.stdout))
                failed = len(re.findall(r"FAILED", result.stdout))
                results["passed"] = passed
                results["failed"] = failed
                results["total"] = passed + failed
                results["stdout"] = result.stdout
                results["stderr"] = result.stderr
            except Exception as e:
                results["error"] = str(e)

        for expected_file in task.expected_files:
            file_path = Path(workspace_path) / expected_file
            results["details"].append({
                "file": expected_file,
                "exists": file_path.exists(),
                "size": file_path.stat().st_size if file_path.exists() else 0,
            })

        return results
