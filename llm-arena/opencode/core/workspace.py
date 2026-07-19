"""Per-agent isolated workspaces.

Every arena contestant gets a unique directory tree. Tools and the agent
only operate inside that tree (path jail). Concurrent models never share
writable paths.
"""

from __future__ import annotations

import os
import re
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


def _safe_segment(name: str) -> str:
    """Filesystem-safe single path segment."""
    cleaned = re.sub(r"[^\w.\-]+", "_", name.strip()) or "agent"
    return cleaned[:80]


@dataclass
class AgentWorkspace:
    """Isolated workspace for one model run."""

    run_id: str
    model_id: str
    task_id: str
    root: Path  # unique root for this agent

    @property
    def src_dir(self) -> Path:
        """Writable working directory exposed to tools as working_dir."""
        return self.root / "src"

    @property
    def meta_path(self) -> Path:
        return self.root / "workspace.json"

    def ensure(self) -> None:
        self.src_dir.mkdir(parents=True, exist_ok=True)
        self.meta_path.write_text(
            (
                "{\n"
                f'  "run_id": "{self.run_id}",\n'
                f'  "model_id": "{self.model_id}",\n'
                f'  "task_id": "{self.task_id}",\n'
                f'  "src": "{self.src_dir.as_posix()}"\n'
                "}\n"
            ),
            encoding="utf-8",
        )


class WorkspaceManager:
    """Allocate unique per-agent directories under a base root."""

    def __init__(self, base_dir: Optional[str | Path] = None):
        if base_dir is None:
            # Prefer project data/workspaces next to cwd (llm-arena/)
            base = Path(os.environ.get("OPENCODE_WORKSPACES", "data/workspaces"))
        else:
            base = Path(base_dir)
        self.base_dir = base.resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def create(
        self,
        *,
        model_id: str,
        task_id: str,
        run_id: Optional[str] = None,
        arena_id: Optional[str] = None,
    ) -> AgentWorkspace:
        """Create a brand-new isolated workspace for one agent run."""
        rid = run_id or uuid.uuid4().hex[:12]
        # Layout:
        #   data/workspaces/{arena_or_batch}/{model_id}__{run_id}/
        batch = _safe_segment(arena_id or "runs")
        folder = f"{_safe_segment(model_id)}__{rid}"
        root = self.base_dir / batch / folder
        # Extremely unlikely collision: add suffix
        if root.exists():
            root = self.base_dir / batch / f"{folder}_{uuid.uuid4().hex[:6]}"
        ws = AgentWorkspace(
            run_id=rid,
            model_id=model_id,
            task_id=task_id,
            root=root,
        )
        ws.ensure()
        return ws

    def cleanup(self, workspace: AgentWorkspace, keep: bool = False) -> None:
        if keep:
            return
        if workspace.root.exists() and self.base_dir in workspace.root.resolve().parents:
            shutil.rmtree(workspace.root, ignore_errors=True)


def resolve_in_workspace(working_dir: str, path: str) -> Path:
    """Resolve path under working_dir; reject escapes via .. or absolute paths."""
    base = Path(working_dir).resolve()
    # Treat absolute client paths as relative to workspace root name only
    raw = Path(path)
    if raw.is_absolute():
        # strip drive/root — only allow the final parts relative to base
        candidate = base / raw.name
    else:
        candidate = (base / raw).resolve()

    try:
        candidate.relative_to(base)
    except ValueError as exc:
        raise PermissionError(
            f"Path escapes agent workspace: {path!r} (base={base})"
        ) from exc
    return candidate


# Process-wide default manager
DEFAULT_WORKSPACE_MANAGER = WorkspaceManager()
