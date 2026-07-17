"""FastAPI server for OpenCode Arena.

Fair multi-model arena under single-variable constraints:
only model identity + credentials differ between contestants.
"""

from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from opencode.core.arena_runner import ArenaConfig, ArenaRunner
from opencode.core.container_runner import ContainerRunner
from opencode.core.fairness import DEFAULT_CONSTRAINTS
from opencode.core.run_store import STORE
from opencode.core.task_runner import TaskRunner

# Load .env from project root (llm-arena/)
load_dotenv(Path(__file__).resolve().parents[2] / ".env")


# Global state
runner: Optional[ArenaRunner] = None
task_runner: Optional[TaskRunner] = None
container_runner: Optional[ContainerRunner] = None

PROVIDER_ENV_KEYS = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "google": "GOOGLE_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "mimo": "MIMO_API_KEY",
    "custom": "OPENAI_API_KEY",
}

DEFAULT_BASE_URLS = {
    "mimo": os.environ.get("MIMO_BASE_URL", "https://api.xiaomimimo.com/v1"),
    "deepseek": os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
}


def resolve_api_key(provider: str, api_key: Optional[str] = None) -> str:
    if api_key and str(api_key).strip():
        return str(api_key).strip()
    env_name = PROVIDER_ENV_KEYS.get(provider, f"{provider.upper()}_API_KEY")
    return os.environ.get(env_name, "") or ""


def resolve_base_url(provider: str, base_url: Optional[str] = None) -> Optional[str]:
    if base_url and str(base_url).strip():
        return str(base_url).strip()
    return DEFAULT_BASE_URLS.get(provider)


def _parse_model_entry(raw: dict) -> dict:
    """Normalize a model contestant: only identity + credentials allowed."""
    model_id = raw.get("model_id") or raw.get("id") or raw.get("modelId")
    provider = raw.get("provider") or raw.get("model_provider") or "custom"
    version = raw.get("version") or raw.get("model_version") or model_id
    if not model_id:
        raise HTTPException(status_code=400, detail="Each model requires model_id")
    api_key = resolve_api_key(provider, raw.get("api_key") or raw.get("apiKey"))
    if not api_key:
        env_name = PROVIDER_ENV_KEYS.get(provider, f"{provider.upper()}_API_KEY")
        raise HTTPException(
            status_code=400,
            detail=(
                f"API key required for model '{model_id}' (provider '{provider}'). "
                f"Configure in UI or set {env_name}."
            ),
        )
    base_url = resolve_base_url(
        provider, raw.get("base_url") or raw.get("baseUrl")
    )
    # Explicitly drop temperature / max_tokens / system_prompt from client
    return {
        "model_id": model_id,
        "provider": provider,
        "version": version,
        "api_key": api_key,
        "base_url": base_url,
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    global runner, task_runner, container_runner

    task_runner = TaskRunner(tasks_dir="tasks")
    try:
        container_runner = ContainerRunner()
    except Exception as exc:
        print(f"Warning: Docker unavailable at startup: {exc}")
        container_runner = None

    # Always create runner — falls back to local in-process agent when no Docker
    runner = ArenaRunner(task_runner, container_runner)
    print(
        f"Arena ready (docker={'yes' if container_runner and container_runner.client else 'no'}, "
        f"constraints={DEFAULT_CONSTRAINTS.fingerprint()})"
    )

    yield

    if container_runner:
        try:
            container_runner.cleanup()
        except Exception:
            pass


app = FastAPI(
    title="OpenCode Arena API",
    description="Fair multi-model coding agent arena (single-variable principle)",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "version": "0.2.0",
        "docker": bool(container_runner and getattr(container_runner, "client", None)),
        "constraints_fingerprint": DEFAULT_CONSTRAINTS.fingerprint(),
    }


@app.get("/api/v1/constraints")
async def get_constraints():
    """Public frozen control variables (single-variable principle)."""
    c = DEFAULT_CONSTRAINTS
    return {
        "fingerprint": c.fingerprint(),
        "constraints": c.to_public_dict(),
        "variable_allowed": ["model_id", "provider", "version", "api_key", "base_url"],
        "variable_forbidden": [
            "temperature",
            "max_tokens",
            "system_prompt",
            "max_steps",
            "timeout",
            "tools",
        ],
        "note": "Only model identity and API credentials may differ between contestants.",
    }


@app.get("/api/v1/models")
async def list_models():
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


@app.get("/api/v1/tasks")
async def list_tasks(language: Optional[str] = None, difficulty: Optional[str] = None):
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


@app.post("/api/v1/runs")
async def start_run(data: dict):
    """Start a single-model run (still uses frozen constraints)."""
    if not runner or not task_runner:
        raise HTTPException(status_code=503, detail="Arena not initialized")

    task_id = data.get("task_id")
    if not task_id:
        raise HTTPException(status_code=400, detail="task_id required")

    entry = _parse_model_entry(
        {
            "model_id": data.get("model_id"),
            "provider": data.get("provider") or data.get("model_provider"),
            "version": data.get("version") or data.get("model_version"),
            "api_key": data.get("api_key") or data.get("apiKey"),
            "base_url": data.get("base_url") or data.get("baseUrl"),
        }
    )

    task = task_runner.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    fp = DEFAULT_CONSTRAINTS.fingerprint()
    stored = STORE.create_run(
        model_id=entry["model_id"],
        task_id=task_id,
        provider=entry["provider"],
        version=entry["version"],
        constraints_fingerprint=fp,
    )

    try:
        result = await runner.run_single(
            task=task,
            model_id=entry["model_id"],
            model_provider=entry["provider"],
            model_version=entry["version"],
            api_key=entry["api_key"],
            base_url=entry["base_url"],
        )
        agent = result.agent_result
        status = "completed" if result.status in ("success", "completed") else "failed"
        STORE.finish_run(
            stored.id,
            status=status,
            duration=getattr(agent, "total_duration", None),
            tokens_used=getattr(agent, "total_tokens", None),
            test_results=result.test_results or {},
            error=getattr(agent, "error", None),
        )
    except Exception as exc:
        STORE.finish_run(stored.id, status="failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    run = STORE.runs[stored.id]
    return STORE.to_public_run(run)


@app.post("/api/v1/arena")
async def start_arena(data: dict):
    """Start a multi-model fair arena match (single-variable principle).

    Body:
      task_id: str
      models: [{model_id, provider, version, api_key?, base_url?}, ...]
      parallel: bool (default true)

    Client-supplied temperature / max_tokens / system_prompt are ignored.
    """
    if not runner or not task_runner:
        raise HTTPException(status_code=503, detail="Arena not initialized")

    task_id = data.get("task_id")
    models_raw = data.get("models") or []
    parallel = data.get("parallel", True)

    if not task_id:
        raise HTTPException(status_code=400, detail="task_id required")
    if not isinstance(models_raw, list) or len(models_raw) < 2:
        raise HTTPException(
            status_code=400,
            detail="At least 2 models required for an arena match (single-variable comparison).",
        )

    task = task_runner.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    entries = [_parse_model_entry(m) for m in models_raw]
    model_ids = [e["model_id"] for e in entries]
    if len(set(model_ids)) != len(model_ids):
        raise HTTPException(status_code=400, detail="Duplicate model_id in arena models")

    model_configs = {
        e["model_id"]: {
            "provider": e["provider"],
            "version": e["version"],
            "api_key": e["api_key"],
            "base_url": e["base_url"],
        }
        for e in entries
    }

    constraints = DEFAULT_CONSTRAINTS
    arena = STORE.create_arena(
        task_id=task_id,
        model_ids=model_ids,
        constraints=constraints.to_public_dict(),
        constraints_fingerprint=constraints.fingerprint(),
        parallel=bool(parallel),
    )

    run_records = []
    for e in entries:
        r = STORE.create_run(
            model_id=e["model_id"],
            task_id=task_id,
            provider=e["provider"],
            version=e["version"],
            constraints_fingerprint=constraints.fingerprint(),
            arena_id=arena.id,
        )
        arena.run_ids.append(r.id)
        run_records.append((e["model_id"], r.id))

    config = ArenaConfig(
        task_id=task_id,
        model_ids=model_ids,
        max_steps=constraints.max_steps,
        timeout=constraints.timeout,
        parallel=bool(parallel),
    )

    try:
        arena_result = await runner.run_arena(config, model_configs)
    except Exception as exc:
        arena.status = "failed"
        for _, rid in run_records:
            STORE.finish_run(rid, status="failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Map results back to stored runs
    by_model = {tr.model_id: tr for tr in arena_result.results}
    public_runs = []
    for model_id, rid in run_records:
        tr = by_model.get(model_id)
        if not tr:
            STORE.finish_run(rid, status="failed", error="No result returned")
        else:
            agent = tr.agent_result
            status = "completed" if tr.status in ("success", "completed") else "failed"
            STORE.finish_run(
                rid,
                status=status,
                duration=getattr(agent, "total_duration", None),
                tokens_used=getattr(agent, "total_tokens", None),
                test_results=tr.test_results or {},
                error=getattr(agent, "error", None),
            )
        public_runs.append(STORE.to_public_run(STORE.runs[rid]))

    arena.status = "completed"
    arena.completed_at = arena_result.end_time
    report = runner.generate_report(arena_result)

    return {
        "arena_id": arena.id,
        "task_id": task_id,
        "status": arena.status,
        "parallel": arena.parallel,
        "constraints_fingerprint": arena.constraints_fingerprint,
        "constraints": {
            "fingerprint": arena.constraints_fingerprint,
            "system_prompt_version": constraints.system_prompt_version,
            "tool_protocol_version": constraints.tool_protocol_version,
            "temperature": constraints.temperature,
            "max_tokens": constraints.max_tokens,
            "max_steps": constraints.max_steps,
            "timeout": constraints.timeout,
        },
        "runs": public_runs,
        "report": report,
    }


@app.get("/api/v1/arena/{arena_id}")
async def get_arena(arena_id: str):
    arena = STORE.arenas.get(arena_id)
    if not arena:
        raise HTTPException(status_code=404, detail="Arena not found")
    runs = [STORE.to_public_run(STORE.runs[rid]) for rid in arena.run_ids if rid in STORE.runs]
    return {
        "arena_id": arena.id,
        "task_id": arena.task_id,
        "status": arena.status,
        "model_ids": arena.model_ids,
        "constraints_fingerprint": arena.constraints_fingerprint,
        "constraints": arena.constraints,
        "runs": runs,
    }


@app.get("/api/v1/runs")
async def list_runs(
    model_id: Optional[str] = None,
    task_id: Optional[str] = None,
    status: Optional[str] = None,
):
    runs = STORE.list_runs(model_id=model_id, task_id=task_id, status=status)
    return {"runs": [STORE.to_public_run(r) for r in runs]}


@app.get("/api/v1/runs/{run_id}")
async def get_run(run_id: str):
    run = STORE.runs.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return STORE.to_public_run(run)


@app.post("/api/v1/runs/{run_id}/cancel")
async def cancel_run(run_id: str):
    if container_runner:
        try:
            container_runner.cleanup(run_id)
        except Exception:
            pass
    run = STORE.runs.get(run_id)
    if run and run.status == "running":
        STORE.finish_run(run_id, status="failed", error="cancelled")
    return {"status": "cancelled", "run_id": run_id}


@app.get("/api/v1/leaderboard")
async def get_leaderboard(type: str = "overall"):
    """Leaderboard from completed runs only (no simulated scores)."""
    completed = STORE.list_runs(status="completed")
    by_model: dict[str, dict[str, Any]] = {}
    for run in completed:
        entry = by_model.setdefault(
            run.model_id,
            {
                "modelId": run.model_id,
                "model_id": run.model_id,
                "runs": 0,
                "completedRuns": 0,
                "passRate": 0.0,
                "hiddenPassRate": 0.0,
                "avgTokens": 0.0,
                "avgCost": 0.0,
                "avgDuration": 0.0,
                "stability": 0.0,
                "codeQuality": None,
                "safetyScore": None,
                "overallScore": 0.0,
                "constraints_fingerprints": set(),
            },
        )
        entry["runs"] += 1
        entry["completedRuns"] += 1
        entry["avgTokens"] += run.tokens_used or 0
        entry["avgDuration"] += run.duration or 0
        tr = run.test_results or {}
        total = tr.get("total") or 0
        passed = tr.get("passed") or 0
        if total:
            entry["passRate"] += passed / total
        entry["constraints_fingerprints"].add(run.constraints_fingerprint)

    entries = []
    for mid, e in by_model.items():
        n = e["completedRuns"] or 1
        e["avgTokens"] /= n
        e["avgDuration"] /= n
        e["passRate"] = (e["passRate"] / n) * 100
        e["stability"] = 100.0  # only completed counted here
        # Overall from real metrics only
        e["overallScore"] = e["passRate"] * 0.7 + e["stability"] * 0.3
        e["constraints_fingerprints"] = list(e["constraints_fingerprints"])
        entries.append(e)

    entries.sort(key=lambda x: x["overallScore"], reverse=True)
    return {"type": type, "entries": entries}


@app.get("/api/v1/comparison")
async def compare_models(model_ids: Optional[list[str]] = None):
    """Compare models using stored runs that share the same constraints fingerprint."""
    ids = model_ids or []
    runs = STORE.list_runs(status="completed")
    if ids:
        runs = [r for r in runs if r.model_id in ids]

    # Prefer runs under the same fingerprint
    by_fp: dict[str, list] = {}
    for r in runs:
        by_fp.setdefault(r.constraints_fingerprint, []).append(r)

    best_fp = ""
    best_runs: list = []
    for fp, group in by_fp.items():
        if len(group) > len(best_runs):
            best_fp = fp
            best_runs = group

    metrics = {}
    for r in best_runs:
        tr = r.test_results or {}
        total = tr.get("total") or 0
        passed = tr.get("passed") or 0
        metrics[r.model_id] = {
            "pass_rate": (passed / total * 100) if total else None,
            "tokens": r.tokens_used,
            "duration": r.duration,
            "constraints_fingerprint": r.constraints_fingerprint,
        }

    return {
        "models": ids,
        "constraints_fingerprint": best_fp,
        "metrics": metrics,
        "note": "Only runs with identical constraints_fingerprint are fairly comparable.",
    }


@app.websocket("/ws/runs/{run_id}")
async def websocket_run(websocket: WebSocket, run_id: str):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            run = STORE.runs.get(run_id)
            if message.get("type") == "status":
                await websocket.send_json(
                    {
                        "run_id": run_id,
                        "status": run.status if run else message.get("status"),
                        "timestamp": message.get("timestamp"),
                    }
                )
    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.send_json({"error": str(e)})
    finally:
        await websocket.close()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
