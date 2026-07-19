"""Task runner: load tasks, prepare workspaces, evaluate with pytest."""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .agent import AgentResult
from .tracks import TRACK_IDS, infer_track, normalize_track


_TASK_ID_RE = re.compile(r"^[a-z][a-z0-9_-]{1,63}$")


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
    # Created via API / UI (safe to delete from admin UI)
    custom: bool = False


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
        self.tasks = {}
        if not self.tasks_dir.exists():
            return

        for task_file in self.tasks_dir.rglob("task.json"):
            try:
                with open(task_file, "r", encoding="utf-8") as f:
                    task_data = json.load(f)
            except Exception:
                continue
            lang = task_data.get("language", "")
            typ = task_data.get("type", "")
            track = infer_track(lang, typ, task_data.get("track"))
            task = Task(
                id=task_data["id"],
                name=task_data["name"],
                description=task_data["description"],
                language=lang,
                type=typ,
                difficulty=task_data.get("difficulty", "medium"),
                test_cases=task_data.get("test_cases", 0),
                source_path=str(task_file.parent),
                expected_files=task_data.get("expected_files", []),
                hidden_tests=task_data.get("hidden_tests", []),
                track=track,
                custom=bool(task_data.get("custom", False)),
            )
            self.tasks[task.id] = task

    def reload(self) -> int:
        """Rescan tasks/ on disk. Returns number of loaded tasks."""
        self._load_tasks()
        return len(self.tasks)

    def get_task(self, task_id: str) -> Optional[Task]:
        return self.tasks.get(task_id)

    @staticmethod
    def validate_task_id(task_id: str) -> str:
        tid = (task_id or "").strip().lower()
        if not _TASK_ID_RE.match(tid):
            raise ValueError(
                "task id must be 2–64 chars: start with a letter, then [a-z0-9_-] "
                f"(got {task_id!r})"
            )
        return tid

    def _lang_bucket(self, language: str) -> str:
        lang = (language or "python").lower().strip()
        if lang in ("html", "css", "javascript", "typescript", "js", "ts", "htm"):
            return "html"
        if lang in ("python", "py"):
            return "python"
        # keep other languages under their own folder name
        safe = re.sub(r"[^a-z0-9_-]+", "-", lang).strip("-") or "misc"
        return safe

    def create_task(
        self,
        *,
        task_id: str,
        name: str,
        description: str,
        language: str = "python",
        type_: str = "feature",
        difficulty: str = "medium",
        track: Optional[str] = None,
        expected_files: Optional[list[str]] = None,
        files: Optional[dict[str, str]] = None,
        hidden_tests: Optional[list[dict]] = None,
        test_cases: int = 0,
        custom: bool = True,
        overwrite: bool = False,
    ) -> Task:
        """Write a new task directory under tasks/ and register it in memory."""
        tid = self.validate_task_id(task_id)
        if tid in self.tasks and not overwrite:
            raise FileExistsError(f"task already exists: {tid}")

        lang = (language or "python").lower().strip()
        typ = (type_ or "feature").lower().strip()
        diff = (difficulty or "medium").lower().strip()
        if diff not in ("easy", "medium", "hard"):
            raise ValueError("difficulty must be easy|medium|hard")

        tr = normalize_track(track) if track else None
        if tr == "all":
            tr = None
        effective_track = infer_track(lang, typ, tr or track)
        if effective_track not in TRACK_IDS:
            effective_track = "feature"

        file_map = dict(files or {})
        if "task.json" in file_map:
            raise ValueError("files must not include task.json (generated automatically)")

        # Ensure at least one test file for evaluation
        has_test = any(
            Path(n).name.startswith("test_") and n.endswith(".py")
            or n.endswith("_test.py")
            for n in file_map
        )
        if not has_test:
            raise ValueError("files must include a pytest file (test_*.py)")

        exp = list(expected_files or sorted(file_map.keys()))
        if not test_cases:
            # rough count: test_ def occurrences
            test_cases = 0
            for n, content in file_map.items():
                if "test_" in Path(n).name and n.endswith(".py"):
                    test_cases += len(re.findall(r"^\s*def test_", content, re.M))

        bucket = self._lang_bucket(lang)
        dest = self.tasks_dir / bucket / tid
        if dest.exists() and not overwrite:
            raise FileExistsError(f"task directory already exists: {dest}")
        if dest.exists() and overwrite:
            shutil.rmtree(dest)
        dest.mkdir(parents=True, exist_ok=True)

        meta: dict[str, Any] = {
            "id": tid,
            "name": (name or tid).strip(),
            "description": (description or "").strip(),
            "language": lang,
            "type": typ,
            "difficulty": diff,
            "test_cases": max(0, int(test_cases or 0)),
            "expected_files": exp,
            "hidden_tests": hidden_tests or [],
            "track": effective_track,
            "custom": bool(custom),
        }
        (dest / "task.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        for rel, content in file_map.items():
            rel_path = Path(rel.replace("\\", "/"))
            if rel_path.is_absolute() or ".." in rel_path.parts:
                raise ValueError(f"invalid file path: {rel}")
            out = dest / rel_path
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(content if content is not None else "", encoding="utf-8")

        self.reload()
        task = self.tasks.get(tid)
        if not task:
            raise RuntimeError("task written but failed to reload")
        return task

    def delete_task(self, task_id: str, *, force: bool = False) -> None:
        """Delete a custom task directory. Built-in tasks require force=True."""
        tid = self.validate_task_id(task_id)
        task = self.tasks.get(tid)
        if not task:
            raise FileNotFoundError(f"task not found: {tid}")
        if not task.custom and not force:
            raise PermissionError(
                f"task {tid!r} is built-in; pass force=true to delete anyway"
            )
        src = Path(task.source_path)
        if not src.exists():
            self.reload()
            return
        # safety: only delete under tasks_dir
        try:
            src.resolve().relative_to(self.tasks_dir.resolve())
        except ValueError as exc:
            raise PermissionError("refusing to delete path outside tasks/") from exc
        shutil.rmtree(src)
        self.reload()

    def read_task_files(self, task_id: str) -> dict[str, Any]:
        """Return task.json + text file contents for the editor."""
        task = self.get_task(task_id)
        if not task:
            raise FileNotFoundError(f"task not found: {task_id}")
        root = Path(task.source_path)
        files: dict[str, str] = {}
        for p in sorted(root.rglob("*")):
            if not p.is_file():
                continue
            if p.name == "task.json":
                continue
            if p.suffix.lower() in {".pyc", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico"}:
                continue
            if "__pycache__" in p.parts:
                continue
            rel = p.relative_to(root).as_posix()
            try:
                files[rel] = p.read_text(encoding="utf-8")
            except Exception:
                continue
        meta = json.loads((root / "task.json").read_text(encoding="utf-8"))
        return {"task": meta, "files": files, "source_path": str(root)}

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
