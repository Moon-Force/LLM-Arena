"""FastAPI server for OpenCode Arena.

Provides REST API and WebSocket endpoints for:
- Managing models and tasks
- Running arena comparisons
- Streaming real-time updates
- Serving results
"""

from __future__ import annotations

import asyncio
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from opencode.core.agent import OpenCodeAgent, AgentStatus
from opencode.core.container_runner import ContainerConfig, ContainerRunner
from opencode.core.task_runner import TaskRunner
from opencode.core.arena_runner import ArenaConfig, ArenaRunner

# Load .env from project root (llm-arena/)
load_dotenv(Path(__file__).resolve().parents[2] / ".env")


# Global state
runner: Optional[ArenaRunner] = None
task_runner: Optional[TaskRunner] = None
container_runner: Optional[ContainerRunner] = None

# Provider -> default env var for API key fallback
PROVIDER_ENV_KEYS = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "google": "GOOGLE_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "mimo": "MIMO_API_KEY",
    "custom": "OPENAI_API_KEY",
}


def resolve_api_key(provider: str, api_key: Optional[str] = None) -> str:
    """Prefer request-provided key; fall back to provider env var."""
    if api_key and str(api_key).strip():
        return str(api_key).strip()
    env_name = PROVIDER_ENV_KEYS.get(provider, f"{provider.upper()}_API_KEY")
    return os.environ.get(env_name, "") or ""


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan."""
    global runner, task_runner, container_runner

    # Startup
    task_runner = TaskRunner(tasks_dir="tasks")
    try:
        container_runner = ContainerRunner()
    except Exception as exc:
        # Allow API to boot without Docker; runs will fail until Docker is available
        print(f"Warning: Docker unavailable at startup: {exc}")
        container_runner = None
    if container_runner is not None:
        runner = ArenaRunner(task_runner, container_runner)
    else:
        runner = None

    yield

    # Shutdown
    if container_runner:
        container_runner.cleanup()


app = FastAPI(
    title="OpenCode Arena API",
    description="API for running LLM coding agent comparisons",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check
@app.get("/health")
async def health():
    return {"status": "healthy", "version": "0.1.0"}


# Models
@app.get("/api/v1/models")
async def list_models():
    """List available models."""
    return {
        "models": [
            {
                "id": "claude-opus",
                "name": "Claude Opus",
                "provider": "anthropic",
                "version": "claude-3-opus-20240229",
                "description": "Most capable Claude model for complex tasks",
            },
            {
                "id": "claude-sonnet",
                "name": "Claude Sonnet",
                "provider": "anthropic",
                "version": "claude-3-5-sonnet-20241022",
                "description": "Balanced performance and speed",
            },
            {
                "id": "gpt-4o",
                "name": "GPT-4o",
                "provider": "openai",
                "version": "gpt-4o",
                "description": "OpenAI flagship multimodal model",
            },
            {
                "id": "gemini-pro",
                "name": "Gemini Pro",
                "provider": "google",
                "version": "gemini-1.5-pro",
                "description": "Google advanced reasoning model",
            },
            {
                "id": "deepseek-chat",
                "name": "DeepSeek Chat",
                "provider": "deepseek",
                "version": "deepseek-chat",
                "description": "Efficient open-weight model",
            },
            {
                "id": "mimo-v2.5-pro",
                "name": "MiMo V2.5 Pro",
                "provider": "mimo",
                "version": "mimo-v2.5-pro",
                "description": "Xiaomi MiMo flagship (OpenAI-compatible)",
                "baseUrl": "https://api.xiaomimimo.com/v1",
            },
        ]
    }


# Tasks
@app.get("/api/v1/tasks")
async def list_tasks(language: Optional[str] = None, difficulty: Optional[str] = None):
    """List available tasks."""
    if task_runner:
        tasks = task_runner.list_tasks(language=language, difficulty=difficulty)
    else:
        tasks = []

    return {
        "tasks": [
            {
                "id": t.id,
                "name": t.name,
                "description": t.description,
                "language": t.language,
                "type": t.type,
                "difficulty": t.difficulty,
                "test_cases": t.test_cases,
            }
            for t in tasks
        ]
    }


# Runs
@app.post("/api/v1/runs")
async def start_run(data: dict):
    """Start a new arena run.

    Accepts per-request model credentials from the frontend:
    - api_key / apiKey: preferred source (configured in UI)
    - provider, version, base_url: model identity / endpoint
    Falls back to process env vars when api_key is omitted.
    """
    if not runner:
        raise HTTPException(
            status_code=503,
            detail="Arena not initialized (Docker may be unavailable)",
        )

    model_id = data.get("model_id")
    task_id = data.get("task_id")
    max_steps = data.get("max_steps", 100)
    timeout = data.get("timeout", 300)

    if not model_id or not task_id:
        raise HTTPException(status_code=400, detail="model_id and task_id required")

    provider = (
        data.get("provider")
        or data.get("model_provider")
        or "anthropic"
    )
    version = (
        data.get("version")
        or data.get("model_version")
        or "claude-3-opus-20240229"
    )
    base_url = data.get("base_url") or data.get("baseUrl")
    if not base_url:
        if provider == "mimo":
            base_url = os.environ.get("MIMO_BASE_URL", "https://api.xiaomimimo.com/v1")
        elif provider == "deepseek":
            base_url = os.environ.get(
                "DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"
            )
    api_key = resolve_api_key(
        provider,
        data.get("api_key") or data.get("apiKey"),
    )

    if not api_key:
        env_name = PROVIDER_ENV_KEYS.get(provider, f"{provider.upper()}_API_KEY")
        raise HTTPException(
            status_code=400,
            detail=(
                f"API key required for provider '{provider}'. "
                f"Set it in Model Configuration, or set the {env_name} environment variable."
            ),
        )

    # Get task
    task = task_runner.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    # Run task (api_key comes from frontend config or env fallback)
    result = await runner.run_single(
        task=task,
        model_id=model_id,
        model_provider=provider,
        model_version=version,
        api_key=api_key,
        max_steps=max_steps,
        timeout=timeout,
        base_url=base_url,
    )

    return {
        "run_id": result.agent_result.run_id if hasattr(result.agent_result, 'run_id') else str(hash(result)),
        "status": result.status,
        "task_id": task_id,
        "model_id": model_id,
    }


@app.get("/api/v1/runs")
async def list_runs(
    model_id: Optional[str] = None,
    task_id: Optional[str] = None,
    status: Optional[str] = None,
):
    """List arena runs."""
    # In a real implementation, this would query a database
    return {"runs": []}


@app.get("/api/v1/runs/{run_id}")
async def get_run(run_id: str):
    """Get a specific run."""
    # In a real implementation, this would query a database
    return {"run_id": run_id, "status": "completed"}


@app.post("/api/v1/runs/{run_id}/cancel")
async def cancel_run(run_id: str):
    """Cancel a running task."""
    if container_runner:
        container_runner.cleanup(run_id)
    return {"status": "cancelled", "run_id": run_id}


# Leaderboard
@app.get("/api/v1/leaderboard")
async def get_leaderboard(type: str = "overall"):
    """Get leaderboard."""
    # In a real implementation, this would query results
    return {
        "type": type,
        "entries": [],
    }


# Comparison
@app.get("/api/v1/comparison")
async def compare_models(model_ids: list[str] = None):
    """Compare models."""
    return {
        "models": model_ids or [],
        "metrics": {},
    }


# WebSocket for real-time updates
@app.websocket("/ws/runs/{run_id}")
async def websocket_run(websocket: WebSocket, run_id: str):
    """WebSocket endpoint for real-time run updates."""
    await websocket.accept()

    try:
        while True:
            # In a real implementation, this would stream logs from the container
            data = await websocket.receive_text()
            message = json.loads(data)

            # Process message
            if message.get("type") == "status":
                await websocket.send_json({
                    "run_id": run_id,
                    "status": message.get("status"),
                    "timestamp": message.get("timestamp"),
                })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.send_json({"error": str(e)})
    finally:
        await websocket.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
