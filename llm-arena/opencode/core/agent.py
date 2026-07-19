"""Result types shared by the Arena runtime.

The agent loop itself is the official opencode-ai binary (see opencode_runtime.py).
These dataclasses only describe run outcomes for the store / UI.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class AgentStatus(Enum):
    IDLE = "idle"
    THINKING = "thinking"
    ACTING = "acting"
    TESTING = "testing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class AgentStep:
    step_number: int
    thought: str = ""
    action: str = ""
    observation: str = ""
    tool_calls: list[dict] = field(default_factory=list)
    duration_ms: float = 0.0
    tokens_used: int = 0
    tools_completed: int = 0


@dataclass
class AgentResult:
    status: AgentStatus
    steps: list[AgentStep]
    final_code: str = ""
    test_results: dict = field(default_factory=dict)
    total_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_duration: float = 0.0
    error: Optional[str] = None
    run_id: str = ""
