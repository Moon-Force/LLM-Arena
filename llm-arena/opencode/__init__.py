"""OpenCode - A unified Coding Agent framework for LLM Arena.

This module provides the core infrastructure for running coding agents
in controlled environments, supporting multiple LLM models.
"""

__version__ = "0.1.0"
__all__ = [
    "OpenCodeAgent",
    "ToolRegistry",
    "TaskRunner",
    "ContainerRunner",
    "ModelClient",
    "ArenaRunner",
]

from .core.agent import OpenCodeAgent
from .core.tool_registry import ToolRegistry
from .core.task_runner import TaskRunner
from .core.container_runner import ContainerRunner
from .core.model_client import ModelClient
from .core.arena_runner import ArenaRunner
