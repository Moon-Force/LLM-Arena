"""Core agent implementation for OpenCode.

The OpenCodeAgent is the main orchestrator that manages the agent loop:
1. Receives a task description
2. Uses LLM to plan and execute code changes
3. Manages tool calls (read, write, test, etc.)
4. Evaluates results and iterates
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

from .tool_registry import ToolRegistry
from .model_client import ModelClient


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


class OpenCodeAgent:
    """Main agent class that orchestrates the coding task.

    The agent follows a ReAct (Reasoning + Acting) pattern:
    1. THINK: Analyze the current state and plan next steps
    2. ACT: Execute a tool (read file, write file, run test, etc.)
    3. OBSERVE: Get the result of the action
    4. Repeat until task is complete or max steps reached
    """

    def __init__(
        self,
        model_client: ModelClient,
        tool_registry: ToolRegistry,
        max_steps: int = 100,
        system_prompt: Optional[str] = None,
    ):
        self.model = model_client
        self.tools = tool_registry
        self.max_steps = max_steps
        self.system_prompt = system_prompt or self._default_system_prompt()
        self.status = AgentStatus.IDLE
        self.steps: list[AgentStep] = []
        self._callbacks: list[Callable] = []

    def _default_system_prompt(self) -> str:
        return """You are an expert coding assistant. Your task is to:
1. Understand the given coding task
2. Read the existing code if any
3. Make necessary changes to fix bugs or implement features
4. Run tests to verify your changes
5. Continue iterating until all tests pass

You have access to tools for reading/writing files and running commands.
Always think step by step and explain your reasoning.
"""

    def on_step(self, callback: Callable[[AgentStep], None]) -> None:
        """Register a callback to be called on each step."""
        self._callbacks.append(callback)

    async def run(self, task_description: str, working_dir: str) -> AgentResult:
        """Run the agent on a task.

        Args:
            task_description: Description of the coding task
            working_dir: Directory to work in

        Returns:
            AgentResult with the final status and outputs
        """
        self.status = AgentStatus.THINKING
        self.steps = []
        start_time = time.time()
        total_tokens = 0

        try:
            # Initialize conversation with system prompt and task
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": task_description},
            ]

            for step_num in range(self.max_steps):
                step = AgentStep(step_number=step_num)
                step_start = time.time()

                # THINK: Get LLM response
                self.status = AgentStatus.THINKING
                response = await self.model.chat(messages)
                step.thought = response.get("content", "")
                step.tokens_used = response.get("usage", {}).get("total_tokens", 0)
                total_tokens += step.tokens_used

                # Check if task is complete
                if "FINISHED" in step.thought or "COMPLETE" in step.thought:
                    self.status = AgentStatus.COMPLETED
                    break

                # ACT: Parse and execute tool calls
                self.status = AgentStatus.ACTING
                tool_calls = self._parse_tool_calls(step.thought)
                step.tool_calls = tool_calls

                for tool_call in tool_calls:
                    result = await self.tools.execute(
                        tool_call["name"],
                        tool_call.get("arguments", {}),
                        working_dir=working_dir,
                    )
                    step.observation = str(result)

                # Update messages for next iteration
                messages.append({"role": "assistant", "content": step.thought})
                if step.observation:
                    messages.append({"role": "user", "content": f"Observation: {step.observation}"})

                step.duration_ms = (time.time() - step_start) * 1000
                self.steps.append(step)

                # Notify callbacks
                for callback in self._callbacks:
                    callback(step)

            else:
                # Max steps reached
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
        """Parse tool calls from LLM response.

        Expected format:
        ```tool
        {"name": "read_file", "arguments": {"path": "src/main.py"}}
        ```
        """
        tool_calls = []
        import re

        # Match code blocks with tool syntax
        pattern = r'```tool\n(.*?)\n```'
        matches = re.findall(pattern, text, re.DOTALL)

        for match in matches:
            try:
                tool_call = json.loads(match)
                tool_calls.append(tool_call)
            except json.JSONDecodeError:
                continue

        return tool_calls
