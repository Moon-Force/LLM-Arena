"""Tool registry for managing available tools.

Tools are functions that the agent can call to interact with the environment.
Each tool has a name, description, schema, and implementation.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import os
import subprocess
from dataclasses import dataclass
from typing import Any, Callable, Optional


@dataclass
class Tool:
    """Definition of a tool."""
    name: str
    description: str
    parameters: dict  # JSON schema for parameters
    handler: Callable  # Function to execute


class ToolRegistry:
    """Registry of available tools for the agent."""

    def __init__(self):
        self._tools: dict[str, Tool] = {}
        self._register_default_tools()

    def _register_default_tools(self) -> None:
        """Register the default set of coding tools."""
        self.register(
            name="read_file",
            description="Read the contents of a file",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file"},
                },
                "required": ["path"],
            },
            handler=self._read_file,
        )

        self.register(
            name="write_file",
            description="Write content to a file",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file"},
                    "content": {"type": "string", "description": "Content to write"},
                },
                "required": ["path", "content"],
            },
            handler=self._write_file,
        )

        self.register(
            name="list_directory",
            description="List files in a directory",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the directory"},
                },
                "required": ["path"],
            },
            handler=self._list_directory,
        )

        self.register(
            name="run_command",
            description="Run a shell command",
            parameters={
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Command to run"},
                    "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 30},
                },
                "required": ["command"],
            },
            handler=self._run_command,
        )

        self.register(
            name="run_tests",
            description="Run the test suite",
            parameters={
                "type": "object",
                "properties": {
                    "test_path": {"type": "string", "description": "Path to test file or directory"},
                },
                "required": ["test_path"],
            },
            handler=self._run_tests,
        )

        self.register(
            name="search_code",
            description="Search for patterns in code files",
            parameters={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Pattern to search for"},
                    "path": {"type": "string", "description": "Path to search in"},
                },
                "required": ["pattern", "path"],
            },
            handler=self._search_code,
        )

    def register(
        self,
        name: str,
        description: str,
        parameters: dict,
        handler: Callable,
    ) -> None:
        """Register a new tool."""
        self._tools[name] = Tool(
            name=name,
            description=description,
            parameters=parameters,
            handler=handler,
        )

    async def execute(self, name: str, arguments: dict, **context) -> Any:
        """Execute a tool by name.

        Args:
            name: Tool name
            arguments: Tool arguments
            **context: Additional context (e.g., working_dir)

        Returns:
            Tool execution result
        """
        if name not in self._tools:
            return {"error": f"Tool '{name}' not found"}

        tool = self._tools[name]

        try:
            # Check if handler is async
            if asyncio.iscoroutinefunction(tool.handler):
                return await tool.handler(**arguments, **context)
            else:
                return tool.handler(**arguments, **context)
        except Exception as e:
            return {"error": str(e)}

    def get_tool_definitions(self) -> list[dict]:
        """Get tool definitions for LLM context."""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            }
            for tool in self._tools.values()
        ]

    # Tool implementations

    @staticmethod
    def _read_file(path: str, **context) -> dict:
        """Read a file and return its contents."""
        working_dir = context.get("working_dir", ".")
        full_path = os.path.join(working_dir, path)

        try:
            with open(full_path, "r", encoding="utf-8") as f:
                return {"content": f.read(), "path": path}
        except FileNotFoundError:
            return {"error": f"File not found: {path}"}
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def _write_file(path: str, content: str, **context) -> dict:
        """Write content to a file."""
        working_dir = context.get("working_dir", ".")
        full_path = os.path.join(working_dir, path)

        try:
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)
            return {"success": True, "path": path, "bytes_written": len(content)}
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def _list_directory(path: str = ".", **context) -> dict:
        """List files in a directory."""
        working_dir = context.get("working_dir", ".")
        full_path = os.path.join(working_dir, path)

        try:
            items = []
            for item in os.listdir(full_path):
                item_path = os.path.join(full_path, item)
                items.append({
                    "name": item,
                    "type": "directory" if os.path.isdir(item_path) else "file",
                    "size": os.path.getsize(item_path) if os.path.isfile(item_path) else None,
                })
            return {"items": items, "path": path}
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def _run_command(command: str, timeout: int = 30, **context) -> dict:
        """Run a shell command."""
        working_dir = context.get("working_dir", ".")

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=working_dir,
            )
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
                "command": command,
            }
        except subprocess.TimeoutExpired:
            return {"error": f"Command timed out after {timeout}s"}
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def _run_tests(test_path: str, **context) -> dict:
        """Run tests using pytest."""
        working_dir = context.get("working_dir", ".")

        try:
            result = subprocess.run(
                f"python -m pytest {test_path} -v --tb=short",
                shell=True,
                capture_output=True,
                text=True,
                timeout=60,
                cwd=working_dir,
            )

            # Parse pytest output
            import re
            passed = len(re.findall(r'PASSED', result.stdout))
            failed = len(re.findall(r'FAILED', result.stdout))

            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
                "passed": passed,
                "failed": failed,
                "total": passed + failed,
            }
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def _search_code(pattern: str, path: str, **context) -> dict:
        """Search for patterns in code files."""
        working_dir = context.get("working_dir", ".")
        search_path = os.path.join(working_dir, path)

        try:
            import re
            matches = []

            for root, _, files in os.walk(search_path):
                for filename in files:
                    if filename.endswith(('.py', '.ts', '.js', '.java', '.cpp', '.c', '.go', '.rs')):
                        file_path = os.path.join(root, filename)
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                for line_num, line in enumerate(f, 1):
                                    if re.search(pattern, line):
                                        matches.append({
                                            "file": os.path.relpath(file_path, working_dir),
                                            "line": line_num,
                                            "content": line.strip(),
                                        })
                        except Exception:
                            continue

            return {"matches": matches, "count": len(matches)}
        except Exception as e:
            return {"error": str(e)}
