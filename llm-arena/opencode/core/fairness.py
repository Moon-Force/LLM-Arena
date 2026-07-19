"""Single-variable (control-variable) constraints for fair arena runs.

Only model identity + credentials (api_key / base_url) may differ between
contestants. Everything else is frozen and versioned for reproducibility.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


# Bump when system prompt or tool protocol changes (invalidates old comparisons).
SYSTEM_PROMPT_VERSION = "opencode-official-sys-v1"
TOOL_PROTOCOL_VERSION = "opencode-ai-builtin-tools-v1"
ARENA_ENGINE_VERSION = "arena-engine-official-opencode-v1"

# Used when official OpenCode runs as the agent engine (default).
# OpenCode already has bash/read/write/edit/grep/glob tools — no fenced-tool protocol.
FROZEN_SYSTEM_PROMPT = """You are OpenCode running in a controlled multi-model coding benchmark (LLM Arena).

Workflow:
1. Explore the workspace with OpenCode tools (read / glob / grep / list / bash)
2. Implement or fix the task (Python or HTML/CSS/JS UI) via write / edit / apply_patch
3. You may use webfetch / websearch for docs if needed
4. Run tests with bash: python -m pytest -v --tb=short
5. Fix failures and re-test until they pass
6. When all tests pass, reply with exactly: FINISHED

Official tools available: bash, read, write, edit, apply_patch, glob, grep, list,
webfetch, websearch, todowrite, skill, lsp, task.

Rules:
- Stay inside the project workspace directory.
- Keep required element ids/classes exact (tests assert them).
- Do not leave stub/TODO placeholder pages as the final result.
- Prefer one complete index.html with embedded CSS/JS for UI tasks when appropriate.
- Do not ask the user questions — this is an unattended benchmark run.
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
    agent_engine: str = "opencode-ai"

    def to_public_dict(self) -> dict[str, Any]:
        """Snapshot safe to store/return (includes full prompt for audit)."""
        return asdict(self)

    def fingerprint(self) -> str:
        """Short fingerprint of frozen knobs (excluding long prompt body)."""
        return (
            f"{self.arena_engine_version}|"
            f"{self.system_prompt_version}|"
            f"{self.tool_protocol_version}|"
            f"engine={self.agent_engine}|"
            f"t={self.temperature}|tok={self.max_tokens}|"
            f"steps={self.max_steps}|timeout={self.timeout}"
        )


# Singleton used by all fair runs unless tests inject another instance.
DEFAULT_CONSTRAINTS = FrozenConstraints()
