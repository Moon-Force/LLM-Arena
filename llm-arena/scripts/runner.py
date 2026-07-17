#!/usr/bin/env python3
"""OpenCode Arena Runner Script.

This script runs inside Docker containers to execute coding tasks.
It connects to the LLM, runs the agent loop, and reports results.
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

# Add opencode to path
sys.path.insert(0, "/workspace")

from opencode.core.agent import OpenCodeAgent
from opencode.core.model_client import ModelClient
from opencode.core.tool_registry import ToolRegistry


async def main():
    """Main runner entry point."""
    # Get configuration from environment
    model_id = os.environ.get("MODEL_ID", "unknown")
    model_provider = os.environ.get("MODEL_PROVIDER", "anthropic")
    model_version = os.environ.get("MODEL_VERSION", "claude-3-opus-20240229")
    max_steps = int(os.environ.get("MAX_STEPS", "100"))
    timeout = int(os.environ.get("TIMEOUT", "300"))

    # Get API key: provider-specific env, generic API_KEY, or OpenAI alias
    api_key = (
        os.environ.get(f"{model_provider.upper()}_API_KEY", "")
        or os.environ.get("API_KEY", "")
        or os.environ.get("OPENAI_API_KEY", "")
        or os.environ.get("ANTHROPIC_API_KEY", "")
        or os.environ.get("GOOGLE_API_KEY", "")
        or os.environ.get("DEEPSEEK_API_KEY", "")
        or os.environ.get("MIMO_API_KEY", "")
    )
    base_url = (
        os.environ.get("BASE_URL", "")
        or os.environ.get("OPENAI_BASE_URL", "")
        or os.environ.get("MIMO_BASE_URL", "")
        or None
    )

    # Read task description
    task_path = "/workspace/task"
    task_file = Path(task_path) / "task.json"

    if not task_file.exists():
        print("ERROR: No task.json found", file=sys.stderr)
        sys.exit(1)

    with open(task_file, "r") as f:
        task = json.load(f)

    task_description = task.get("description", "")
    working_dir = "/workspace/src"

    # Initialize model client
    try:
        model = ModelClient.create(
            provider=model_provider,
            api_key=api_key,
            model_version=model_version,
            base_url=base_url,
        )
    except Exception as e:
        print(f"ERROR: Failed to create model client: {e}", file=sys.stderr)
        sys.exit(1)

    # Initialize tools
    tools = ToolRegistry()

    # Initialize agent
    agent = OpenCodeAgent(
        model_client=model,
        tool_registry=tools,
        max_steps=max_steps,
    )

    # Run the task
    print(f"Starting task: {task.get('name', 'Unknown')}")
    print(f"Model: {model_id} ({model_version})")
    print(f"Max steps: {max_steps}")
    print("-" * 50)

    start_time = time.time()

    try:
        result = await agent.run(
            task_description=task_description,
            working_dir=working_dir,
        )

        # Report results
        duration = time.time() - start_time
        print("-" * 50)
        print(f"Status: {result.status.value}")
        print(f"Steps: {len(result.steps)}")
        print(f"Duration: {duration:.2f}s")
        print(f"Tokens: {result.total_tokens}")

        if result.error:
            print(f"Error: {result.error}", file=sys.stderr)
            sys.exit(1)

        # Write results to file
        results_file = Path("/workspace/results/result.json")
        results_file.parent.mkdir(parents=True, exist_ok=True)

        with open(results_file, "w") as f:
            json.dump({
                "status": result.status.value,
                "steps": len(result.steps),
                "duration": duration,
                "tokens": result.total_tokens,
                "error": result.error,
            }, f, indent=2)

        print(f"Results written to {results_file}")

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
