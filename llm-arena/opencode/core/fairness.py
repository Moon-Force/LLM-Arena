"""Single-variable (control-variable) constraints for fair arena runs.

Only model identity + credentials (api_key / base_url) may differ between
contestants. Everything else is frozen and versioned for reproducibility.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


# Bump when system prompt or tool protocol changes (invalidates old comparisons).
SYSTEM_PROMPT_VERSION = "opencode-sys-v1"
TOOL_PROTOCOL_VERSION = "fenced-tool-json-v1"
ARENA_ENGINE_VERSION = "arena-engine-v1"

FROZEN_SYSTEM_PROMPT = """You are an expert coding assistant in a controlled benchmark.
Your task is to:
1. Understand the given coding task
2. Read the existing code if any
3. Make necessary changes to fix bugs or implement features
4. Run tests to verify your changes
5. Continue iterating until all tests pass

You have access to tools. To call a tool, output a fenced block exactly like:
```tool
{"name": "tool_name", "arguments": {...}}
```

Available tools: read_file, write_file, list_directory, run_command.

When the task is fully done and tests pass, reply with the word FINISHED.
Always think step by step. Do not change temperature or invent extra tools.
"""


@dataclass(frozen=True)
class FrozenConstraints:
    """Immutable control variables shared by all models in one arena match."""

    system_prompt_version: str = SYSTEM_PROMPT_VERSION
    tool_protocol_version: str = TOOL_PROTOCOL_VERSION
    arena_engine_version: str = ARENA_ENGINE_VERSION
    system_prompt: str = FROZEN_SYSTEM_PROMPT
    temperature: float = 0.0
    max_tokens: int = 4096
    max_steps: int = 100
    timeout: int = 300
    memory_limit: str = "2g"
    cpu_limit: float = 2.0
    container_image: str = "opencode-model:latest"

    def to_public_dict(self) -> dict[str, Any]:
        """Snapshot safe to store/return (includes full prompt for audit)."""
        return asdict(self)

    def fingerprint(self) -> str:
        """Short fingerprint of frozen knobs (excluding long prompt body)."""
        return (
            f"{self.arena_engine_version}|"
            f"{self.system_prompt_version}|"
            f"{self.tool_protocol_version}|"
            f"t={self.temperature}|tok={self.max_tokens}|"
            f"steps={self.max_steps}|timeout={self.timeout}|"
            f"mem={self.memory_limit}|cpu={self.cpu_limit}|"
            f"img={self.container_image}"
        )


# Singleton used by all fair runs unless tests inject another instance.
DEFAULT_CONSTRAINTS = FrozenConstraints()
