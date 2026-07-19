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
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

from opencode.core.arena_runner import ArenaConfig, ArenaRunner
from opencode.core.fairness import DEFAULT_CONSTRAINTS
from opencode.core.run_store import STORE
from opencode.core.task_runner import TaskRunner

# Load .env from project root (llm-arena/)
load_dotenv(Path(__file__).resolve().parents[2] / ".env")


# Global state
runner: Optional[ArenaRunner] = None
task_runner: Optional[TaskRunner] = None

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
    global runner, task_runner

    task_runner = TaskRunner(tasks_dir="tasks")
    # Agent engine: official opencode-ai only (opencode serve)
    runner = ArenaRunner(task_runner)
    print(
        f"Arena ready (engine=opencode-ai, "
        f"constraints={DEFAULT_CONSTRAINTS.fingerprint()})"
    )

    yield


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
        "engine": "opencode-ai",
        "constraints_fingerprint": DEFAULT_CONSTRAINTS.fingerprint(),
    }


@app.get("/api/v1/constraints")
async def get_constraints():
    """Public frozen control variables (single-variable principle)."""
    from opencode.core.opencode_tools import public_tools_payload

    c = DEFAULT_CONSTRAINTS
    tools = public_tools_payload()
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
        "note": (
            "Only model identity and API credentials may differ between contestants. "
            "All contestants use the same official OpenCode tool set. "
            "Tracks partition the task pool only — not free variables per model."
        ),
        "opencode": tools,
        "variable_principle": {
            "allowed": ["model_id", "provider", "version", "api_key", "base_url"],
            "frozen": [
                "system_prompt",
                "tools",
                "temperature",
                "max_tokens",
                "max_steps",
                "timeout",
                "track_tools_policy",
            ],
            "track_note": (
                "track selects which tasks are compared; every model in a match "
                "shares the same track, tools, and frozen knobs."
            ),
        },
    }


@app.get("/api/v1/opencode/tools")
async def get_opencode_tools():
    """List official OpenCode tools enabled for arena runs."""
    from opencode.core.opencode_tools import public_tools_payload

    return public_tools_payload()


@app.get("/api/v1/tracks")
async def list_tracks():
    """Evaluation tracks (task-pool partitions). Same tools within a track."""
    from opencode.core.tracks import list_public_tracks, track_note

    counts = task_runner.count_by_track() if task_runner else {}
    return {
        "tracks": list_public_tracks(counts),
        "note": track_note(),
    }


@app.get("/api/v1/secrets")
async def get_secrets():
    """Load provider API keys / base URLs from project .env (for frontend sync).

    Local-dev helper: returns full keys so the UI can display and edit them.
    Do not expose this endpoint on public networks without auth.
    """
    from opencode.core.env_config import read_provider_secrets

    return read_provider_secrets()


@app.put("/api/v1/secrets")
async def put_secrets(data: dict):
    """Write provider secrets from frontend into .env and process env.

    Body:
      {
        "updates": [
          { "provider": "deepseek", "api_key": "sk-...", "base_url": "..." },
          { "provider": "mimo", "api_key": "sk-..." }
        ]
      }
    """
    from opencode.core.env_config import write_provider_secrets

    updates = data.get("updates") or data.get("providers") or []
    if isinstance(updates, dict):
        # allow { "deepseek": { "api_key": "..." }, ... }
        updates = [
            {"provider": k, **(v if isinstance(v, dict) else {"api_key": v})}
            for k, v in updates.items()
        ]
    if not isinstance(updates, list) or not updates:
        raise HTTPException(status_code=400, detail="updates list required")
    try:
        return write_provider_secrets(updates)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


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
                "id": "deepseek-v4-pro",
                "name": "DeepSeek V4 Pro",
                "provider": "deepseek",
                "version": "deepseek-v4-pro",
                "description": "DeepSeek-V4-Pro flagship (agentic coding, 1M context)",
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
async def list_tasks(
    language: Optional[str] = None,
    difficulty: Optional[str] = None,
    track: Optional[str] = None,
):
    if task_runner:
        tasks = task_runner.list_tasks(
            language=language, difficulty=difficulty, track=track
        )
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
                "testCases": t.test_cases,
                "track": t.track,
                "trackId": t.track,
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
        track=task.track,
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
        from opencode.core.agent_serialize import format_agent_log, serialize_agent_steps

        STORE.finish_run(
            stored.id,
            status=status,
            duration=getattr(agent, "total_duration", None),
            tokens_used=getattr(agent, "total_tokens", None),
            input_tokens=getattr(agent, "input_tokens", None),
            output_tokens=getattr(agent, "output_tokens", None),
            test_results=result.test_results or {},
            error=getattr(agent, "error", None),
            workspace_path=getattr(result, "workspace_path", "") or "",
            agent_steps=serialize_agent_steps(agent),
            agent_log=format_agent_log(agent, getattr(result, "code_diff", "") or ""),
        )
    except Exception as exc:
        STORE.finish_run(stored.id, status="failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    run = STORE.runs[stored.id]
    return STORE.to_public_run(run)


@app.post("/api/v1/arena")
async def start_arena(data: dict, background_tasks: BackgroundTasks):
    """Start a multi-model fair arena match (single-variable principle).

    Body:
      task_id: str
      track: optional — must match task.track if set (task-pool partition only)
      models: [{model_id, provider, version, api_key?, base_url?}, ...]
      parallel: bool (default true)

    Only model identity + credentials may differ. Same track/tools/frozen knobs
    for every contestant.
    """
    from opencode.core.tracks import track_note, validate_task_track

    if not runner or not task_runner:
        raise HTTPException(status_code=503, detail="Arena not initialized")

    task_id = data.get("task_id")
    models_raw = data.get("models") or []
    parallel = data.get("parallel", True)
    requested_track = data.get("track") or data.get("trackId")

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

    try:
        effective_track = validate_task_track(task.track, requested_track)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

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
        track=effective_track,
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
            track=effective_track,
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

    # Map model_id -> store run id so each agent step can stream into STORE
    store_run_ids = {model_id: rid for model_id, rid in run_records}
    arena_runner = runner  # capture for background thread

    def _execute_arena_in_thread() -> None:
        """Run arena in a fresh event loop (threadpool) so FastAPI stays free."""
        import asyncio
        import time as _time
        import traceback

        async def _execute_arena() -> None:
            assert arena_runner is not None
            try:
                arena_result = await arena_runner.run_arena(
                    config, model_configs, store_run_ids=store_run_ids
                )
            except Exception as exc:
                arena.status = "failed"
                arena.completed_at = _time.time()
                for _, rid in run_records:
                    if STORE.runs.get(rid) and STORE.runs[rid].status == "running":
                        STORE.finish_run(rid, status="failed", error=str(exc))
                print(f"[arena] background failed: {exc}")
                traceback.print_exc()
                return

            from opencode.core.agent_serialize import format_agent_log, serialize_agent_steps

            by_model = {tr.model_id: tr for tr in arena_result.results}
            for model_id, rid in run_records:
                tr = by_model.get(model_id)
                if not tr:
                    STORE.finish_run(rid, status="failed", error="No result returned")
                    continue
                agent = tr.agent_result
                status = "completed" if tr.status in ("success", "completed") else "failed"
                STORE.finish_run(
                    rid,
                    status=status,
                    duration=getattr(agent, "total_duration", None),
                    tokens_used=getattr(agent, "total_tokens", None),
                    input_tokens=getattr(agent, "input_tokens", None),
                    output_tokens=getattr(agent, "output_tokens", None),
                    test_results=tr.test_results or {},
                    error=getattr(agent, "error", None),
                    workspace_path=getattr(tr, "workspace_path", "") or "",
                    agent_steps=serialize_agent_steps(agent),
                    agent_log=format_agent_log(agent, getattr(tr, "code_diff", "") or ""),
                )
            arena.status = "completed"
            arena.completed_at = arena_result.end_time
            print(f"[arena] completed {arena.id}")

        try:
            asyncio.run(_execute_arena())
        except Exception as exc:
            print(f"[arena] thread crashed: {exc}")
            traceback.print_exc()
            arena.status = "failed"
            for _, rid in run_records:
                if STORE.runs.get(rid) and STORE.runs[rid].status == "running":
                    STORE.finish_run(rid, status="failed", error=str(exc))

    # After HTTP response is sent, Starlette runs this in a worker thread
    background_tasks.add_task(_execute_arena_in_thread)

    public_runs = [STORE.to_public_run(STORE.runs[rid]) for _, rid in run_records]
    print(f"[arena] started {arena.id} runs={[rid for _, rid in run_records]}")

    return {
        "arena_id": arena.id,
        "task_id": task_id,
        "track": effective_track,
        "trackId": effective_track,
        "status": "running",
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
        "single_variable_note": track_note(),
        "runs": public_runs,
        "report": None,
        "live": True,
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
        "track": arena.track or "",
        "trackId": arena.track or "",
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
    track: Optional[str] = None,
):
    runs = STORE.list_runs(
        model_id=model_id, task_id=task_id, status=status, track=track
    )
    return {"runs": [STORE.to_public_run(r) for r in runs]}


@app.get("/api/v1/runs/{run_id}")
async def get_run(run_id: str):
    run = STORE.runs.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return STORE.to_public_run(run)


@app.post("/api/v1/runs/{run_id}/cancel")
async def cancel_run(run_id: str):
    run = STORE.runs.get(run_id)
    if run and run.status == "running":
        STORE.finish_run(run_id, status="failed", error="cancelled")
    return {"status": "cancelled", "run_id": run_id}


@app.get("/api/v1/leaderboard")
async def get_leaderboard(type: str = "overall", track: str = "all"):
    """Leaderboard from completed runs only (no simulated scores).

    `track` partitions scores by evaluation content. Within a track, all runs
    share the same frozen tools/constraints (single-variable principle).
    """
    completed = STORE.list_runs(status="completed", track=track if track != "all" else None)
    # Backfill track from task if older runs lack the field
    if track and track != "all" and task_runner:
        filled = []
        for run in STORE.list_runs(status="completed"):
            rt = run.track
            if not rt:
                t = task_runner.get_task(run.task_id)
                rt = t.track if t else ""
            if rt == track:
                filled.append(run)
        completed = filled

    by_model: dict[str, dict[str, Any]] = {}
    for run in completed:
        entry = by_model.setdefault(
            run.model_id,
            {
                "modelId": run.model_id,
                "model_id": run.model_id,
                "track": track if track != "all" else (run.track or "all"),
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
        ht = tr.get("hidden_total") or tr.get("hiddenTotal") or 0
        hp = tr.get("hidden_passed") or tr.get("hiddenPassed") or 0
        if ht:
            entry["hiddenPassRate"] += hp / ht
        entry["constraints_fingerprints"].add(run.constraints_fingerprint)

    entries = []
    for mid, e in by_model.items():
        n = e["completedRuns"] or 1
        e["avgTokens"] /= n
        e["avgDuration"] /= n
        e["passRate"] = (e["passRate"] / n) * 100
        e["hiddenPassRate"] = (e["hiddenPassRate"] / n) * 100
        e["stability"] = 100.0  # only completed counted here
        # Real metrics only — same formula for all models in the track
        primary = e["hiddenPassRate"] if e["hiddenPassRate"] else e["passRate"]
        e["overallScore"] = primary * 0.5 + e["passRate"] * 0.3 + e["stability"] * 0.2
        e["constraints_fingerprints"] = list(e["constraints_fingerprints"])
        e["sampleNote"] = f"n={e['completedRuns']}"
        entries.append(e)

    entries.sort(key=lambda x: x["overallScore"], reverse=True)
    return {
        "type": type,
        "track": track or "all",
        "entries": entries,
        "note": "Scores only comparable within the same track (single-variable frozen tools).",
    }


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


# ---------------------------------------------------------------------------
# Workspace browser — frontend preview of each agent's isolated outputs
# ---------------------------------------------------------------------------

def _resolve_run_src(run_id: str) -> Path:
    from opencode.core.workspace_browser import find_src_for_run_workspace, workspaces_root

    run = STORE.runs.get(run_id)
    if run and run.workspace_path:
        src = find_src_for_run_workspace(run.workspace_path)
        if src and src.exists():
            return src
    # Fallback: newest disk folder for this model_id
    root = workspaces_root()
    if root.exists() and run:
        candidates = [
            agent_dir / "src"
            for agent_dir in root.rglob("*")
            if agent_dir.is_dir()
            and run.model_id in agent_dir.name
            and (agent_dir / "src").is_dir()
        ]
        candidates.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        if candidates:
            return candidates[0].resolve()
    raise HTTPException(status_code=404, detail="Workspace not found for this run")


@app.get("/api/v1/workspaces")
async def list_workspaces():
    """List agent workspaces on disk + in-memory runs (for frontend gallery)."""
    from opencode.core import workspace_browser as wb

    disk = wb.list_disk_workspaces(limit=80)
    runs = [
        {
            **STORE.to_public_run(r),
            "source": "memory",
        }
        for r in STORE.list_runs()
    ]
    return {"workspaces": disk, "runs": runs}


@app.delete("/api/v1/workspaces/{workspace_id:path}")
async def delete_workspace(workspace_id: str):
    """Delete one agent workspace folder (Agent outputs gallery)."""
    from opencode.core import workspace_browser as wb

    try:
        return wb.delete_workspace(workspace_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/v1/workspaces/delete")
async def delete_workspaces_bulk(data: dict):
    """Delete multiple workspaces.

    Body: { "ids": ["runs/model__abc", ...] }
    """
    from opencode.core import workspace_browser as wb

    ids = data.get("ids") or data.get("workspace_ids") or []
    if not isinstance(ids, list) or not ids:
        raise HTTPException(status_code=400, detail="ids required (non-empty list)")
    if len(ids) > 50:
        raise HTTPException(status_code=400, detail="Too many ids (max 50)")
    return wb.delete_workspaces([str(i) for i in ids])


@app.get("/api/v1/runs/{run_id}/files")
async def list_run_files(run_id: str):
    from opencode.core import workspace_browser as wb

    src = _resolve_run_src(run_id)
    try:
        return wb.list_files(src)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/v1/runs/{run_id}/files/content")
async def read_run_file(run_id: str, path: str):
    """Read a file relative to the agent workspace src/."""
    from opencode.core import workspace_browser as wb

    src = _resolve_run_src(run_id)
    try:
        return wb.read_file(src, path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/v1/workspaces/{workspace_id:path}/files")
async def list_workspace_files(workspace_id: str):
    """Browse by disk workspace id: `{batch}/{folder}`."""
    from opencode.core import workspace_browser as wb

    root = wb.workspaces_root() / workspace_id
    src = root / "src" if (root / "src").is_dir() else root
    if not src.exists():
        raise HTTPException(status_code=404, detail="Workspace not found")
    try:
        src.relative_to(wb.workspaces_root().resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Invalid workspace path")
    try:
        data = wb.list_files(src)
        data["workspace_id"] = workspace_id
        data["model_id"] = root.name.split("__")[0] if "__" in root.name else root.name
        return data
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/v1/workspaces/{workspace_id:path}/files/content")
async def read_workspace_file(workspace_id: str, path: str):
    from opencode.core import workspace_browser as wb

    root = wb.workspaces_root() / workspace_id
    src = root / "src" if (root / "src").is_dir() else root
    if not src.exists():
        raise HTTPException(status_code=404, detail="Workspace not found")
    try:
        return wb.read_file(src, path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _preview_base_url(request: Request, workspace_id: str) -> str:
    """Absolute URL prefix for workspace preview assets (ends with /)."""
    # Keep path segments encoded the same way clients call the API
    segs = "/".join(part for part in workspace_id.replace("\\", "/").split("/") if part)
    root = str(request.base_url).rstrip("/")
    return f"{root}/api/v1/workspaces/{segs}/preview/"


@app.get("/api/v1/workspaces/{workspace_id:path}/preview")
@app.get("/api/v1/workspaces/{workspace_id:path}/preview/")
async def preview_workspace_index(workspace_id: str, request: Request):
    """Redirect to the HTML entrypoint under a real static base URL (accurate CSS/JS)."""
    from opencode.core import workspace_browser as wb

    try:
        src = wb.resolve_src_dir(workspace_id)
        entry = wb.pick_html_entrypoint(src)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    base = _preview_base_url(request, workspace_id)
    return RedirectResponse(url=base + entry.lstrip("/"), status_code=307)


@app.get("/api/v1/workspaces/{workspace_id:path}/preview/{asset_path:path}")
async def preview_workspace_asset(workspace_id: str, asset_path: str, request: Request):
    """Serve workspace files over HTTP so relative CSS/JS/images resolve correctly.

    Prefer this over iframe srcdoc (srcdoc cannot load sibling styles.css).
    """
    from opencode.core import workspace_browser as wb
    import mimetypes

    try:
        src = wb.resolve_src_dir(workspace_id)
        target = wb.resolve_preview_file(src, asset_path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    ext = target.suffix.lower()
    mime, _ = mimetypes.guess_type(str(target))
    mime = mime or "application/octet-stream"

    if ext in {".html", ".htm"}:
        raw = target.read_text(encoding="utf-8", errors="replace")
        # Base = directory of this HTML file under /preview/
        parent = str(Path(asset_path).parent).replace("\\", "/")
        if parent in (".", ""):
            base = _preview_base_url(request, workspace_id)
        else:
            base = _preview_base_url(request, workspace_id) + parent.strip("/") + "/"
        html = wb.prepare_html_for_preview(raw, base)
        return HTMLResponse(
            content=html,
            media_type="text/html; charset=utf-8",
            # No X-Frame-Options: allow Vite (3000) to iframe API (8000)
            headers={"Cache-Control": "no-store"},
        )

    return FileResponse(
        path=str(target),
        media_type=mime,
        headers={"Cache-Control": "no-store"},
    )


@app.get("/api/v1/runs/{run_id}/preview")
@app.get("/api/v1/runs/{run_id}/preview/")
@app.get("/api/v1/runs/{run_id}/preview/{asset_path:path}")
async def preview_run_asset(run_id: str, request: Request, asset_path: str = ""):
    """Preview a run's workspace via /runs/{id}/preview/… (same accuracy as workspace preview)."""
    from opencode.core import workspace_browser as wb
    import mimetypes

    try:
        src = _resolve_run_src(run_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    try:
        if not asset_path or asset_path.endswith("/"):
            entry = wb.pick_html_entrypoint(src)
            if not asset_path:
                root = str(request.base_url).rstrip("/")
                return RedirectResponse(
                    url=f"{root}/api/v1/runs/{run_id}/preview/{entry}",
                    status_code=307,
                )
            asset_path = asset_path + entry
        target = wb.resolve_preview_file(src, asset_path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    ext = target.suffix.lower()
    mime, _ = mimetypes.guess_type(str(target))
    mime = mime or "application/octet-stream"
    if ext in {".html", ".htm"}:
        raw = target.read_text(encoding="utf-8", errors="replace")
        parent = str(Path(asset_path).parent).replace("\\", "/")
        root = str(request.base_url).rstrip("/")
        if parent in (".", ""):
            base = f"{root}/api/v1/runs/{run_id}/preview/"
        else:
            base = f"{root}/api/v1/runs/{run_id}/preview/{parent.strip('/')}/"
        return HTMLResponse(
            content=wb.prepare_html_for_preview(raw, base),
            media_type="text/html; charset=utf-8",
            headers={"Cache-Control": "no-store"},
        )
    return FileResponse(path=str(target), media_type=mime, headers={"Cache-Control": "no-store"})


@app.websocket("/ws/runs/{run_id}")
async def websocket_run(websocket: WebSocket, run_id: str):
    """Push live run snapshots (status + agent_steps) as they change until finished."""
    import asyncio
    import hashlib

    await websocket.accept()
    try:
        last_sig = None
        while True:
            run = STORE.runs.get(run_id)
            if run:
                payload = STORE.to_public_run(run)
                # Detect mid-step progress: thought length, tools done, message count, log
                steps = run.agent_steps or []
                last = steps[-1] if steps else {}
                tools_done = 0
                thought_len = 0
                if isinstance(last, dict):
                    tools_done = int(last.get("tools_completed") or 0)
                    thought_len = len(last.get("thought") or "")
                msgs = run.agent_messages or []
                log_tail = (run.agent_log or "")[-200:]
                raw_sig = (
                    f"{run.status}|{len(steps)}|{tools_done}|{thought_len}|"
                    f"{run.tokens_used}|{run.input_tokens}|{run.output_tokens}|"
                    f"{len(msgs)}|{len(run.agent_log or '')}|{log_tail}"
                )
                sig = hashlib.md5(raw_sig.encode("utf-8", errors="ignore")).hexdigest()
                if sig != last_sig:
                    last_sig = sig
                    await websocket.send_json({"type": "run", "run": payload})
                if run.status in ("completed", "failed", "cancelled"):
                    # Final push already sent if sig changed; ensure one last snapshot
                    await websocket.send_json({"type": "run", "run": payload})
                    break
            else:
                await websocket.send_json({"type": "error", "error": "Run not found"})
                break
            # Poll store frequently for progressive step/tool updates
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=0.35)
            except asyncio.TimeoutError:
                pass
    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"error": str(e)})
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
