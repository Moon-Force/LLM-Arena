"""Core agent implementation for OpenCode.

The OpenCodeAgent is the main orchestrator that manages the agent loop:
1. Receives a task description
2. Uses LLM to plan and execute code changes
3. Manages tool calls (read, write, test, etc.)
4. Evaluates results and iterates
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional, Union

from .fairness import DEFAULT_CONSTRAINTS, FrozenConstraints
from .model_client import BaseModelClient, ModelResponse
from .tool_registry import ToolRegistry


class AgentStatus(Enum):
    IDLE = "idle"
    THINKING = "thinking"
    ACTING = "acting"
    TESTING = "testing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class AgentStep:
    """Represents a single step in the agent's execution."""
    step_number: int
    thought: str = ""
    action: str = ""
    observation: str = ""
    tool_calls: list[dict] = field(default_factory=list)
    duration_ms: float = 0.0
    tokens_used: int = 0


@dataclass
class AgentResult:
    """Result of an agent run."""
    status: AgentStatus
    steps: list[AgentStep]
    final_code: str = ""
    test_results: dict = field(default_factory=dict)
    total_tokens: int = 0
    total_duration: float = 0.0
    error: Optional[str] = None
    run_id: str = ""


class OpenCodeAgent:
    """Main agent class that orchestrates the coding task (ReAct loop)."""

    def __init__(
        self,
        model_client: BaseModelClient,
        tool_registry: ToolRegistry,
        max_steps: Optional[int] = None,
        system_prompt: Optional[str] = None,
        constraints: Optional[FrozenConstraints] = None,
    ):
        self.constraints = constraints or DEFAULT_CONSTRAINTS
        self.model = model_client
        self.tools = tool_registry
        # Frozen constraints win over per-call overrides (single-variable principle)
        self.max_steps = (
            self.constraints.max_steps if max_steps is None else min(max_steps, self.constraints.max_steps)
        )
        self.system_prompt = system_prompt or self.constraints.system_prompt
        self.status = AgentStatus.IDLE
        self.steps: list[AgentStep] = []
        self._callbacks: list[Callable] = []

    def on_step(self, callback: Callable[[AgentStep], None]) -> None:
        """Register a callback to be called on each step."""
        self._callbacks.append(callback)

    def _extract_content(self, response: Union[ModelResponse, dict, Any]) -> tuple[str, int]:
        if isinstance(response, ModelResponse):
            usage = response.usage or {}
            return response.content or "", int(usage.get("total_tokens", 0) or 0)
        if isinstance(response, dict):
            content = response.get("content", "") or ""
            usage = response.get("usage") or {}
            return content, int(usage.get("total_tokens", 0) or 0)
        content = getattr(response, "content", "") or str(response)
        usage = getattr(response, "usage", {}) or {}
        return content, int(usage.get("total_tokens", 0) or 0)

    async def run(self, task_description: str, working_dir: str) -> AgentResult:
        """Run the agent on a task with frozen decoding knobs."""
        self.status = AgentStatus.THINKING
        self.steps = []
        start_time = time.time()
        total_tokens = 0

        try:
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": task_description},
            ]

            for step_num in range(self.max_steps):
                step = AgentStep(step_number=step_num)
                step_start = time.time()

                self.status = AgentStatus.THINKING
                response = await self.model.chat(
                    messages,
                    temperature=self.constraints.temperature,
                    max_tokens=self.constraints.max_tokens,
                )
                thought, tokens = self._extract_content(response)
                step.thought = thought
                step.tokens_used = tokens
                total_tokens += tokens

                if "FINISHED" in step.thought.upper() or "COMPLETE" in step.thought.upper():
                    # Only complete if FINISHED is intentional end signal
                    if "FINISHED" in step.thought.upper():
                        self.status = AgentStatus.COMPLETED
                        step.duration_ms = (time.time() - step_start) * 1000
                        self.steps.append(step)
                        break

                self.status = AgentStatus.ACTING
                tool_calls = self._parse_tool_calls(step.thought)
                step.tool_calls = tool_calls

                observations: list[str] = []
                for tool_call in tool_calls:
                    result = await self.tools.execute(
                        tool_call["name"],
                        tool_call.get("arguments", {}),
                        working_dir=working_dir,
                    )
                    observations.append(str(result))
                step.observation = "\n".join(observations)

                messages.append({"role": "assistant", "content": step.thought})
                if step.observation:
                    messages.append(
                        {"role": "user", "content": f"Observation:\n{step.observation}"}
                    )
                elif not tool_calls:
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                "No tool call detected. Use a ```tool fenced JSON block, "
                                "or reply FINISHED if the task is complete."
                            ),
                        }
                    )

                step.duration_ms = (time.time() - step_start) * 1000
                self.steps.append(step)

                for callback in self._callbacks:
                    callback(step)
            else:
                self.status = AgentStatus.FAILED
                return AgentResult(
                    status=AgentStatus.FAILED,
                    steps=self.steps,
                    error="Max steps reached",
                    total_tokens=total_tokens,
                    total_duration=time.time() - start_time,
                )

            return AgentResult(
                status=self.status,
                steps=self.steps,
                total_tokens=total_tokens,
                total_duration=time.time() - start_time,
            )

        except Exception as e:
            self.status = AgentStatus.FAILED
            return AgentResult(
                status=AgentStatus.FAILED,
                steps=self.steps,
                error=str(e),
                total_tokens=total_tokens,
                total_duration=time.time() - start_time,
            )

    def _parse_tool_calls(self, text: str) -> list[dict]:
        """Parse tool calls from LLM response (frozen tool protocol)."""
        tool_calls: list[dict] = []
        pattern = r"```tool\s*\n(.*?)```"
        matches = re.findall(pattern, text, re.DOTALL)

        for match in matches:
            try:
                tool_call = json.loads(match.strip())
                if isinstance(tool_call, dict) and "name" in tool_call:
                    tool_calls.append(tool_call)
            except json.JSONDecodeError:
                continue

        return tool_calls
