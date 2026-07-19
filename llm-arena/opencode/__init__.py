"""LLM Arena — multi-model coding contests powered by official OpenCode.

Agent execution is delegated to opencode-ai (`opencode serve`).
This package provides orchestration, workspaces, evaluation, and the API.
"""

__version__ = "0.2.0"
__all__ = [
    "TaskRunner",
    "ArenaRunner",
]

from .core.task_runner import TaskRunner
from .core.arena_runner import ArenaRunner
