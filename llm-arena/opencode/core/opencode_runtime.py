"""Official OpenCode (opencode-ai) runtime for Arena.

Embeds the real OpenCode agent via `opencode serve` + HTTP/SSE.
No self-built ReAct loop — tools, session, and streaming come from upstream.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import socket
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

import httpx

from .agent import AgentResult, AgentStatus, AgentStep


# ---------------------------------------------------------------------------
# Paths / binary
# ---------------------------------------------------------------------------

def _project_root() -> Path:
    # opencode/core/opencode_runtime.py -> llm-arena/
    return Path(__file__).resolve().parents[2]


def find_opencode_bin() -> str:
    """Resolve opencode CLI: PATH, then local node_modules."""
    env_bin = (os.environ.get("OPENCODE_BIN") or "").strip()
    if env_bin and Path(env_bin).exists():
        return env_bin

    which = shutil.which("opencode")
    if which:
        return which

    root = _project_root()
    # Prefer real .exe over .cmd shims (Windows shell=True quirks)
    candidates = [
        root / "node_modules" / "opencode-ai" / "bin" / "opencode.exe",
        root / "node_modules" / "opencode-ai" / "bin" / "opencode",
        root / "node_modules" / ".bin" / "opencode.exe",
        root / "node_modules" / ".bin" / "opencode.cmd",
        root / "node_modules" / ".bin" / "opencode",
    ]
    for c in candidates:
        if c.exists():
            return str(c)

    # last resort: npx
    npx = shutil.which("npx")
    if npx:
        return f"npx:{npx}"
    raise FileNotFoundError(
        "opencode binary not found. Install with: npm install opencode-ai "
        "or set OPENCODE_BIN to the opencode executable."
    )


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


# ---------------------------------------------------------------------------
# Provider mapping (Arena models → OpenCode provider IDs)
# ---------------------------------------------------------------------------

# Arena provider id → OpenCode provider id
_PROVIDER_MAP = {
    "anthropic": "anthropic",
    "openai": "openai",
    "google": "google",
    "deepseek": "deepseek",
    "mimo": "mimo",
    "custom": "openai",
}

# Providers that are NOT built into OpenCode — register as openai-compatible
_OPENAI_COMPAT_PROVIDERS = {
    "mimo": {
        "name": "Xiaomi MiMo",
        "default_base": "https://api.xiaomimimo.com/v1",
    },
    "custom": {
        "name": "Custom OpenAI-compatible",
        "default_base": "https://api.openai.com/v1",
    },
}

_DEFAULT_BASE_URLS = {
    "mimo": "https://api.xiaomimimo.com/v1",
    "deepseek": "https://api.deepseek.com/v1",
}


def map_provider(provider: str) -> str:
    return _PROVIDER_MAP.get((provider or "custom").lower(), provider or "openai")


def build_opencode_config(
    *,
    provider: str,
    model_version: str,
    api_key: str,
    base_url: Optional[str] = None,
    temperature: float = 0.0,
    max_steps: int = 100,
    system_prompt: Optional[str] = None,
) -> dict[str, Any]:
    """Config injected via OPENCODE_CONFIG_CONTENT for unattended arena runs."""
    raw = (provider or "custom").lower()
    pid = map_provider(provider)
    model_ref = f"{pid}/{model_version}"
    resolved_base = (base_url or "").strip() or _DEFAULT_BASE_URLS.get(raw) or _DEFAULT_BASE_URLS.get(pid)

    provider_opts: dict[str, Any] = {"apiKey": api_key}
    if resolved_base:
        provider_opts["baseURL"] = resolved_base

    provider_block: dict[str, Any] = {"options": provider_opts}

    # MiMo / custom: OpenCode has no native provider — use AI SDK openai-compatible
    compat = _OPENAI_COMPAT_PROVIDERS.get(raw) or (
        _OPENAI_COMPAT_PROVIDERS.get("custom") if resolved_base and pid == "openai" and raw == "custom" else None
    )
    if raw in _OPENAI_COMPAT_PROVIDERS or (raw == "custom" and resolved_base):
        meta = _OPENAI_COMPAT_PROVIDERS.get(raw) or _OPENAI_COMPAT_PROVIDERS["custom"]
        provider_block = {
            "npm": "@ai-sdk/openai-compatible",
            "name": meta["name"],
            "options": provider_opts,
            "models": {
                model_version: {
                    "name": model_version,
                    "tools": True,
                    "tool_call": True,
                }
            },
        }

    # deepseek is built-in but baseURL override still helps
    if pid == "deepseek" and resolved_base:
        provider_block = {"options": provider_opts}

    from .opencode_tools import permission_map

    # Full official OpenCode tool set (see opencode_tools.OPENCODE_TOOLS)
    perms = permission_map()

    cfg: dict[str, Any] = {
        "model": model_ref,
        "autoupdate": False,
        "share": "disabled",
        "snapshot": False,
        "permission": perms,
        "agent": {
            "build": {
                "temperature": temperature,
                "steps": max_steps,
                "permission": {
                    **perms,
                    # Unattended: never block on human questions
                    "question": "deny",
                },
            },
            "plan": {
                "disable": True,
            },
        },
        "provider": {
            pid: provider_block,
        },
    }
    if system_prompt:
        cfg["agent"]["build"]["prompt"] = system_prompt
    return cfg


def preflight_chat_api(
    *,
    base_url: str,
    api_key: str,
    model: str,
    provider_label: str = "provider",
) -> None:
    """Quick OpenAI-compatible chat call so we fail fast (balance/auth/model)."""
    if not base_url or not api_key:
        return
    url = base_url.rstrip("/") + "/chat/completions"
    try:
        r = httpx.post(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 4,
                "temperature": 0,
            },
            timeout=25.0,
        )
    except Exception as exc:
        raise RuntimeError(f"{provider_label} API unreachable ({url}): {exc}") from exc

    if r.status_code == 200:
        return
    body = (r.text or "")[:600]
    # Common vendor errors
    if r.status_code == 402 or "insufficient" in body.lower() or "balance" in body.lower():
        raise RuntimeError(
            f"{provider_label} API error 402: account balance insufficient. "
            f"Top up the key for model '{model}'. Detail: {body}"
        )
    if r.status_code in (401, 403):
        raise RuntimeError(
            f"{provider_label} API auth failed ({r.status_code}) for model '{model}'. "
            f"Check API key. Detail: {body}"
        )
    if r.status_code == 404:
        raise RuntimeError(
            f"{provider_label} model not found: '{model}'. Detail: {body}"
        )
    if r.status_code >= 400:
        raise RuntimeError(
            f"{provider_label} API error {r.status_code} for model '{model}': {body}"
        )


# ---------------------------------------------------------------------------
# Live transcript builder (maps OpenCode messages → Arena UI shape)
# ---------------------------------------------------------------------------

@dataclass
class LiveTranscript:
    """Accumulates OpenCode session messages into Arena agent_steps/messages."""

    model_id: str = ""
    task_prompt: str = ""
    steps: list[dict] = field(default_factory=list)
    messages: list[dict] = field(default_factory=list)
    agent_log: str = ""
    total_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    error: Optional[str] = None
    status: str = "running"
    _step_i: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def seed(self) -> None:
        with self._lock:
            self.messages = []
            if self.task_prompt:
                self.messages.append(
                    {
                        "id": "msg_user",
                        "type": "user",
                        "role": "user",
                        "text": self.task_prompt[:16000],
                    }
                )
            self.messages.append(
                {
                    "id": "msg_sys_start",
                    "type": "system",
                    "role": "system",
                    "text": "Official OpenCode agent starting…",
                }
            )
            self.agent_log = "[OpenCode official] starting…\n"
            self.steps = []

    def apply_messages_payload(self, raw_messages: list[Any]) -> None:
        """Rebuild from GET /session/:id/message list."""
        with self._lock:
            out: list[dict] = []
            if self.task_prompt:
                out.append(
                    {
                        "id": "msg_user",
                        "type": "user",
                        "role": "user",
                        "text": self.task_prompt[:16000],
                    }
                )
            steps: list[dict] = []
            tokens = 0
            in_tok_sum = 0
            out_tok_sum = 0
            step_n = 0
            log_lines = ["[OpenCode official session]"]

            for item in raw_messages:
                if not isinstance(item, dict):
                    continue
                info = item.get("info") or item
                parts = item.get("parts") or []
                role = (info.get("role") or info.get("type") or "").lower()

                if role == "user":
                    text = _parts_text(parts) or info.get("text") or ""
                    if text and text.strip() != self.task_prompt.strip():
                        out.append(
                            {
                                "id": info.get("id") or f"user_{len(out)}",
                                "type": "user",
                                "role": "user",
                                "text": str(text)[:16000],
                            }
                        )
                    continue

                if role != "assistant":
                    continue

                step_n += 1
                content: list[dict] = []
                thought_bits: list[str] = []
                tool_calls: list[dict] = []
                obs_bits: list[str] = []
                tin, tout, tok = _parse_token_usage(info.get("tokens") or info)
                tokens += tok
                in_tok_sum += tin
                out_tok_sum += tout

                for p in parts:
                    if not isinstance(p, dict):
                        continue
                    ptype = p.get("type")
                    if ptype == "text":
                        t = (p.get("text") or "").strip()
                        if t:
                            thought_bits.append(t)
                            content.append(
                                {
                                    "type": "text",
                                    "id": p.get("id") or f"text_{step_n}",
                                    "text": t[:20000],
                                }
                            )
                    elif ptype == "reasoning":
                        t = (p.get("text") or "").strip()
                        if t:
                            content.append(
                                {
                                    "type": "reasoning",
                                    "id": p.get("id") or f"reason_{step_n}",
                                    "text": t[:20000],
                                }
                            )
                    elif ptype == "tool":
                        name = p.get("tool") or p.get("name") or "tool"
                        state = p.get("state") or {}
                        st = (state.get("status") or "completed").lower()
                        inp = state.get("input") or {}
                        outp = state.get("output") or state.get("error") or ""
                        title = (
                            f"Called {name}"
                            if st == "completed"
                            else (f"Running {name}…" if st == "running" else f"Queued {name}")
                        )
                        content.append(
                            {
                                "type": "tool",
                                "id": p.get("id") or p.get("callID") or f"tool_{step_n}_{name}",
                                "name": name,
                                "title": title,
                                "subtitle": _tool_subtitle(name, inp if isinstance(inp, dict) else {}),
                                "state": {
                                    "status": st if st in ("pending", "running", "completed", "error") else "completed",
                                    "input": _truncate_args(inp),
                                    "output": str(outp)[:12000] if outp else "",
                                    "error": state.get("error"),
                                },
                            }
                        )
                        tool_calls.append(
                            {
                                "name": name,
                                "arguments": _truncate_args(inp),
                            }
                        )
                        if outp:
                            obs_bits.append(f"{name}: {str(outp)[:4000]}")

                if content:
                    out.append(
                        {
                            "id": info.get("id") or f"asst_{step_n}",
                            "type": "assistant",
                            "role": "assistant",
                            "agent": info.get("agent") or "build",
                            "model": self.model_id or info.get("modelID"),
                            "step": step_n,
                            "tokens": tok,
                            "input_tokens": tin,
                            "output_tokens": tout,
                            "content": content,
                        }
                    )
                    steps.append(
                        {
                            "step": step_n,
                            "thought": "\n".join(thought_bits)[:20000],
                            "observation": "\n".join(obs_bits)[:20000],
                            "tool_calls": tool_calls,
                            "tokens": tok,
                            "input_tokens": tin,
                            "output_tokens": tout,
                            "duration_ms": 0,
                            "tools_completed": len([t for t in tool_calls if True]),
                        }
                    )
                    log_lines.append(f"\n── assistant step {step_n} ──")
                    if tin or tout:
                        log_lines.append(f"[tokens in={tin} out={tout} total={tok}]")
                    if thought_bits:
                        log_lines.append("\n".join(thought_bits)[:4000])
                    for tc in tool_calls:
                        log_lines.append(f"[tool:{tc.get('name')}]")

                err = info.get("error")
                if err:
                    msg = err.get("data", {}).get("message") if isinstance(err, dict) else str(err)
                    if isinstance(err, dict) and err.get("name"):
                        msg = f"{err.get('name')}: {msg or err}"
                    self.error = str(msg or err)

            if self.error:
                out.append(
                    {
                        "id": "msg_err",
                        "type": "system",
                        "role": "system",
                        "text": f"Error: {self.error}",
                    }
                )

            self.messages = out
            self.steps = steps
            self.total_tokens = tokens
            self.input_tokens = in_tok_sum
            self.output_tokens = out_tok_sum
            self.agent_log = "\n".join(log_lines)
            self._step_i = step_n

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "status": self.status,
                "agent_steps": list(self.steps),
                "agent_messages": list(self.messages),
                "agent_log": self.agent_log,
                "tokens_used": self.total_tokens,
                "input_tokens": self.input_tokens,
                "output_tokens": self.output_tokens,
                "error": self.error,
            }


def _parse_token_usage(tinfo: Any) -> tuple[int, int, int]:
    """Extract (input, output, total) from OpenCode / provider token payloads."""
    if not isinstance(tinfo, dict):
        return 0, 0, 0
    # Nested: { tokens: { input, output, total } } or flat usage fields
    nested = tinfo.get("tokens")
    if isinstance(nested, dict):
        tinfo = nested
    tin = int(
        tinfo.get("input")
        or tinfo.get("input_tokens")
        or tinfo.get("prompt_tokens")
        or tinfo.get("promptTokens")
        or 0
    )
    tout = int(
        tinfo.get("output")
        or tinfo.get("output_tokens")
        or tinfo.get("completion_tokens")
        or tinfo.get("completionTokens")
        or 0
    )
    # Some providers nest reasoning under output cache; keep simple sum
    reasoning = int(tinfo.get("reasoning") or tinfo.get("reasoning_tokens") or 0)
    if reasoning and not tout:
        tout = reasoning
    elif reasoning:
        # reasoning often counted separately; add into output for display
        tout = tout + reasoning if tinfo.get("output") is not None else max(tout, reasoning)
    total = int(tinfo.get("total") or tinfo.get("total_tokens") or 0)
    if not total:
        total = tin + tout
    if total and not tin and not tout:
        # only total known — leave split unknown (0/0) but keep total
        pass
    return tin, tout, total


def _parts_text(parts: list) -> str:
    bits = []
    for p in parts or []:
        if isinstance(p, dict) and p.get("type") == "text":
            bits.append(p.get("text") or "")
    return "\n".join(bits)


def _tool_subtitle(name: str, args: dict) -> str:
    for key in ("path", "filePath", "file", "query", "url", "pattern", "description", "command"):
        val = args.get(key)
        if isinstance(val, str) and val.strip():
            s = val.strip()
            return s if len(s) <= 80 else s[:77] + "…"
    return ""


def _truncate_args(args: Any, limit: int = 400) -> Any:
    if not isinstance(args, dict):
        s = str(args)
        return s[:limit] + ("…" if len(s) > limit else "")
    out = {}
    for k, v in args.items():
        if k == "content" and isinstance(v, str) and len(v) > 200:
            out[k] = v[:200] + f"…({len(v)} chars)"
        else:
            s = str(v)
            out[k] = s[:limit] + ("…" if len(s) > limit else "")
    return out


# ---------------------------------------------------------------------------
# Server process / Docker isolation
# ---------------------------------------------------------------------------

OPENCODE_IMAGE = os.environ.get("OPENCODE_IMAGE", "opencode-arena-agent:latest")
CONTAINER_SERVE_PORT = 4096


@dataclass
class OpencodeServer:
    url: str
    port: int
    workspace: Path
    config: dict
    process: Optional[subprocess.Popen] = None
    container_id: Optional[str] = None
    isolation: str = "process"  # process | docker

    def close(self) -> None:
        if self.container_id:
            try:
                subprocess.run(
                    ["docker", "rm", "-f", self.container_id],
                    capture_output=True,
                    timeout=30,
                )
            except Exception:
                pass
            self.container_id = None
        if self.process is not None:
            try:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
            except Exception:
                pass
            self.process = None


def docker_available() -> bool:
    try:
        r = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=12,
        )
        return r.returncode == 0
    except Exception:
        return False


def ensure_opencode_image(image: str = OPENCODE_IMAGE) -> None:
    """Build isolation image once if missing."""
    inspect = subprocess.run(
        ["docker", "image", "inspect", image],
        capture_output=True,
        timeout=30,
    )
    if inspect.returncode == 0:
        return
    root = _project_root()
    dockerfile = root / "Dockerfile.opencode"
    if not dockerfile.exists():
        raise FileNotFoundError(f"Missing {dockerfile}")
    print(f"[opencode] building isolation image {image} …")
    build = subprocess.run(
        ["docker", "build", "-f", str(dockerfile), "-t", image, str(root)],
        capture_output=True,
        text=True,
        timeout=600,
    )
    if build.returncode != 0:
        raise RuntimeError(
            f"Failed to build {image}:\n{(build.stderr or build.stdout or '')[-2000:]}"
        )
    print(f"[opencode] image ready: {image}")


def _wait_health(url: str, *, timeout: float, is_dead: Callable[[], bool], dead_msg: str) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if is_dead():
            raise RuntimeError(dead_msg)
        try:
            r = httpx.get(f"{url}/global/health", timeout=1.0)
            if r.status_code == 200:
                return
        except Exception:
            pass
        try:
            r = httpx.get(f"{url}/doc", timeout=1.0)
            if r.status_code in (200, 301, 302):
                return
        except Exception:
            pass
        time.sleep(0.25)
    raise RuntimeError(f"Timeout waiting for opencode health at {url}")


def _write_workspace_config(workspace: Path, config: dict) -> None:
    cfg_path = workspace / "opencode.json"
    try:
        cfg_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    except Exception:
        pass


def start_opencode_server_docker(
    workspace: Path,
    config: dict,
    *,
    port: Optional[int] = None,
    timeout: float = 60.0,
    memory: str = "2g",
    cpus: str = "2",
) -> OpencodeServer:
    """Run official OpenCode in an ephemeral container.

    Hard isolation:
    - Only this workspace is bind-mounted (no sibling agent dirs)
    - Separate network namespace / process namespace from host agents
    - Resource limits applied
    - Outbound network kept so the model can call LLM APIs
    """
    import uuid as _uuid

    workspace = Path(workspace).resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    _write_workspace_config(workspace, config)
    ensure_opencode_image(OPENCODE_IMAGE)

    host_port = port or free_port()
    name = f"arena-oc-{_uuid.uuid4().hex[:12]}"
    # Prefer config file inside mount (avoids huge -e payload limits)
    env_args = [
        "-e", "OPENCODE_DISABLE_AUTOUPDATE=1",
        "-e", "CI=1",
        # Enable official websearch (Exa) for all arena containers
        "-e", "OPENCODE_ENABLE_EXA=1",
        "-e", f"OPENCODE_CONFIG_CONTENT={json.dumps(config)}",
    ]

    cmd = [
        "docker", "run", "-d",
        "--name", name,
        # Only this workspace visible inside the container
        "-v", f"{workspace}:/workspace:rw",
        "-w", "/workspace",
        "-p", f"127.0.0.1:{host_port}:{CONTAINER_SERVE_PORT}",
        "--memory", memory,
        "--cpus", cpus,
        # Drop ambient host mounts / privileges (keep network for LLM APIs)
        "--security-opt", "no-new-privileges:true",
        *env_args,
        OPENCODE_IMAGE,
        "opencode", "serve",
        "--hostname", "0.0.0.0",
        "--port", str(CONTAINER_SERVE_PORT),
    ]

    run = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if run.returncode != 0:
        raise RuntimeError(
            f"docker run failed:\n{(run.stderr or run.stdout or '')[-1500:]}"
        )
    container_id = (run.stdout or "").strip() or name
    url = f"http://127.0.0.1:{host_port}"

    try:
        def _dead() -> bool:
            st = subprocess.run(
                ["docker", "inspect", "-f", "{{.State.Running}}", container_id],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return st.returncode != 0 or (st.stdout or "").strip().lower() != "true"

        _wait_health(
            url,
            timeout=timeout,
            is_dead=_dead,
            dead_msg=f"opencode container exited early ({container_id})",
        )
    except Exception as health_exc:
        logs = subprocess.run(
            ["docker", "logs", "--tail", "50", container_id],
            capture_output=True,
            text=True,
            timeout=15,
        )
        log_text = ((logs.stdout or "") + (logs.stderr or ""))[-2000:]
        subprocess.run(["docker", "rm", "-f", container_id], capture_output=True, timeout=30)
        raise RuntimeError(
            f"Docker OpenCode failed to become healthy: {health_exc}\n{log_text}"
        ) from health_exc

    print(f"[opencode] docker isolation container={container_id[:12]} port={host_port} ws={workspace}")
    return OpencodeServer(
        url=url,
        port=host_port,
        workspace=workspace,
        config=config,
        container_id=container_id,
        isolation="docker",
    )


def start_opencode_server_process(
    workspace: Path,
    config: dict,
    *,
    port: Optional[int] = None,
    timeout: float = 30.0,
) -> OpencodeServer:
    """Host-process fallback (logical isolation only — not hard sandbox)."""
    workspace = Path(workspace).resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    _write_workspace_config(workspace, config)

    port = port or free_port()
    bin_path = find_opencode_bin()

    if bin_path.startswith("npx:"):
        npx = bin_path.split(":", 1)[1]
        cmd = [npx, "--yes", "opencode-ai", "serve", f"--hostname=127.0.0.1", f"--port={port}"]
        use_shell = False
    else:
        cmd = [bin_path, "serve", f"--hostname=127.0.0.1", f"--port={port}"]
        use_shell = bin_path.lower().endswith((".cmd", ".bat"))

    env = os.environ.copy()
    env["OPENCODE_CONFIG_CONTENT"] = json.dumps(config)
    env["OPENCODE_DISABLE_AUTOUPDATE"] = "1"
    env["CI"] = "1"
    # Official websearch tool (Exa)
    env["OPENCODE_ENABLE_EXA"] = "1"

    popen_cmd: Any = " ".join(f'"{c}"' if " " in c else c for c in cmd) if use_shell else cmd
    proc = subprocess.Popen(
        popen_cmd,
        cwd=str(workspace),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        shell=use_shell,
    )

    url = f"http://127.0.0.1:{port}"
    output_lines: list[str] = []

    def _reader() -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            output_lines.append(line.rstrip())
            if len(output_lines) > 200:
                del output_lines[:50]

    threading.Thread(target=_reader, daemon=True).start()

    try:
        _wait_health(
            url,
            timeout=timeout,
            is_dead=lambda: proc.poll() is not None,
            dead_msg=f"opencode serve exited early (code={proc.returncode}):\n"
            + "\n".join(output_lines[-30:]),
        )
    except Exception:
        try:
            proc.terminate()
        except Exception:
            pass
        raise

    print(f"[opencode] process isolation port={port} ws={workspace}")
    return OpencodeServer(
        url=url,
        port=port,
        workspace=workspace,
        config=config,
        process=proc,
        isolation="process",
    )


def start_opencode_server(
    workspace: Path,
    config: dict,
    *,
    port: Optional[int] = None,
    timeout: float = 45.0,
) -> OpencodeServer:
    """Start official OpenCode with preferred isolation mode.

    OPENCODE_ISOLATION:
      auto   (default) — Docker hard isolation if available, else process
      docker — require Docker; fail if unavailable
      process — host process only (logical isolation)
    """
    mode = (os.environ.get("OPENCODE_ISOLATION") or "auto").strip().lower()
    memory = os.environ.get("OPENCODE_MEM", "2g")
    cpus = os.environ.get("OPENCODE_CPUS", "2")

    if mode in ("docker", "container", "auto"):
        if docker_available():
            try:
                return start_opencode_server_docker(
                    workspace,
                    config,
                    port=port,
                    timeout=max(timeout, 90.0),
                    memory=memory,
                    cpus=cpus,
                )
            except Exception as exc:
                if mode in ("docker", "container"):
                    raise
                print(f"[opencode] docker isolation failed, falling back to process: {exc}")
        elif mode in ("docker", "container"):
            raise RuntimeError(
                "OPENCODE_ISOLATION=docker but Docker is not available. "
                "Start Docker Desktop or set OPENCODE_ISOLATION=process."
            )

    return start_opencode_server_process(
        workspace, config, port=port, timeout=timeout
    )


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class OpencodeClient:
    """Thin HTTP client for one OpenCode server instance."""

    def __init__(self, base_url: str, directory: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.directory = directory
        self._client = httpx.Client(timeout=httpx.Timeout(30.0, read=600.0))

    def close(self) -> None:
        self._client.close()

    def _headers(self) -> dict[str, str]:
        h = {"Content-Type": "application/json", "Accept": "application/json"}
        # Prefer process cwd from `opencode serve` (started in workspace).
        # Only set directory header when path is pure ASCII — non-ASCII paths
        # (e.g. Chinese) break httpx header encoding on some platforms.
        if self.directory:
            try:
                self.directory.encode("ascii")
                h["x-opencode-directory"] = self.directory
            except UnicodeEncodeError:
                pass
        return h

    def health(self) -> dict:
        r = self._client.get(f"{self.base_url}/global/health", headers=self._headers())
        r.raise_for_status()
        return r.json()

    def set_auth(self, provider_id: str, api_key: str) -> None:
        r = self._client.put(
            f"{self.base_url}/auth/{provider_id}",
            headers=self._headers(),
            json={"type": "api", "key": api_key},
        )
        # non-fatal if already set via config
        if r.status_code >= 400:
            print(f"[opencode] auth.set {provider_id} -> {r.status_code} {r.text[:200]}")

    def create_session(self, title: str = "arena") -> dict:
        r = self._client.post(
            f"{self.base_url}/session",
            headers=self._headers(),
            json={"title": title},
        )
        r.raise_for_status()
        return r.json()

    def prompt(
        self,
        session_id: str,
        *,
        text: str,
        provider_id: str,
        model_id: str,
        agent: str = "build",
        system: Optional[str] = None,
        timeout: float = 300.0,
    ) -> dict:
        body: dict[str, Any] = {
            "agent": agent,
            "model": {"providerID": provider_id, "modelID": model_id},
            "parts": [{"type": "text", "text": text}],
        }
        if system:
            body["system"] = system
        r = self._client.post(
            f"{self.base_url}/session/{session_id}/message",
            headers=self._headers(),
            json=body,
            timeout=httpx.Timeout(30.0, read=timeout),
        )
        r.raise_for_status()
        return r.json()

    def prompt_async(
        self,
        session_id: str,
        *,
        text: str,
        provider_id: str,
        model_id: str,
        agent: str = "build",
        system: Optional[str] = None,
    ) -> None:
        body: dict[str, Any] = {
            "agent": agent,
            "model": {"providerID": provider_id, "modelID": model_id},
            "parts": [{"type": "text", "text": text}],
        }
        if system:
            body["system"] = system
        r = self._client.post(
            f"{self.base_url}/session/{session_id}/prompt_async",
            headers=self._headers(),
            json=body,
        )
        if r.status_code not in (200, 204):
            r.raise_for_status()

    def list_messages(self, session_id: str) -> list:
        r = self._client.get(
            f"{self.base_url}/session/{session_id}/message",
            headers=self._headers(),
        )
        r.raise_for_status()
        data = r.json()
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("data") or data.get("messages") or []
        return []

    def abort(self, session_id: str) -> None:
        try:
            self._client.post(
                f"{self.base_url}/session/{session_id}/abort",
                headers=self._headers(),
            )
        except Exception:
            pass

    def reply_permission(self, session_id: str, permission_id: str, response: str = "once") -> None:
        try:
            self._client.post(
                f"{self.base_url}/session/{session_id}/permissions/{permission_id}",
                headers=self._headers(),
                json={"response": response, "remember": True},
            )
        except Exception:
            pass


# ---------------------------------------------------------------------------
# High-level: run one task with official OpenCode
# ---------------------------------------------------------------------------

@dataclass
class OfficialRunResult:
    status: str  # success | failed
    agent_result: AgentResult
    session_id: str = ""
    server_url: str = ""
    raw_messages: list = field(default_factory=list)


def run_with_official_opencode(
    *,
    workspace: str | Path,
    task_prompt: str,
    model_id: str,
    provider: str,
    model_version: str,
    api_key: str,
    base_url: Optional[str] = None,
    temperature: float = 0.0,
    max_steps: int = 100,
    timeout: int = 300,
    system_prompt: Optional[str] = None,
    store_run_id: Optional[str] = None,
    on_update: Optional[Callable[[dict], None]] = None,
) -> OfficialRunResult:
    """Start official OpenCode, run one coding task, stream transcript updates."""
    ws = Path(workspace).resolve()
    ws.mkdir(parents=True, exist_ok=True)

    pid = map_provider(provider)
    raw_provider = (provider or "").lower()
    resolved_base = (base_url or "").strip() or _DEFAULT_BASE_URLS.get(raw_provider) or _DEFAULT_BASE_URLS.get(pid)

    # Fail fast on bad keys / empty balance (esp. MiMo 402) before starting serve
    if resolved_base and api_key and raw_provider in ("mimo", "custom", "openai", "deepseek"):
        try:
            preflight_chat_api(
                base_url=resolved_base,
                api_key=api_key,
                model=model_version,
                provider_label=provider or pid,
            )
        except Exception as pre_exc:
            # Publish error immediately so UI shows reason instead of empty timeout
            live = LiveTranscript(model_id=model_id, task_prompt=task_prompt)
            live.seed()
            live.error = str(pre_exc)
            live.status = "failed"
            snap = live.snapshot()
            if on_update:
                try:
                    on_update(snap)
                except Exception:
                    pass
            if store_run_id:
                try:
                    from .run_store import STORE

                    STORE.update_run(
                        store_run_id,
                        status="failed",
                        agent_steps=[],
                        agent_messages=snap["agent_messages"],
                        agent_log=f"[preflight] {pre_exc}",
                        workspace_path=str(ws),
                        error=str(pre_exc),
                    )
                except Exception:
                    pass
            return OfficialRunResult(
                status="failed",
                agent_result=AgentResult(
                    status=AgentStatus.FAILED,
                    steps=[],
                    error=str(pre_exc),
                    total_duration=0.0,
                ),
            )

    config = build_opencode_config(
        provider=provider,
        model_version=model_version,
        api_key=api_key,
        base_url=base_url or resolved_base,
        temperature=temperature,
        max_steps=max_steps,
        system_prompt=system_prompt,
    )

    live = LiveTranscript(model_id=model_id, task_prompt=task_prompt)
    live.seed()

    def _publish() -> None:
        snap = live.snapshot()
        if on_update:
            try:
                on_update(snap)
            except Exception:
                pass
        if store_run_id:
            try:
                from .run_store import STORE

                STORE.update_run(
                    store_run_id,
                    status="running",
                    agent_steps=snap["agent_steps"],
                    agent_messages=snap["agent_messages"],
                    agent_log=snap["agent_log"],
                    tokens_used=snap["tokens_used"],
                    input_tokens=snap.get("input_tokens"),
                    output_tokens=snap.get("output_tokens"),
                    workspace_path=str(ws),
                    error=snap.get("error"),
                )
            except Exception as exc:
                print(f"[opencode] store update failed: {exc}")

    _publish()

    server: Optional[OpencodeServer] = None
    client: Optional[OpencodeClient] = None
    session_id = ""
    start = time.time()
    stop_poll = threading.Event()

    try:
        server = start_opencode_server(ws, config, timeout=45.0)
        client = OpencodeClient(server.url, directory=str(ws))
        try:
            client.health()
        except Exception:
            pass

        client.set_auth(pid, api_key)
        # also set raw provider name if different
        if provider != pid:
            client.set_auth(provider, api_key)

        sess = client.create_session(title=f"arena-{model_id}")
        session_id = sess.get("id") or sess.get("sessionID") or ""
        if not session_id:
            raise RuntimeError(f"No session id in response: {sess}")

        def _poll_loop() -> None:
            while not stop_poll.wait(0.8):
                try:
                    msgs = client.list_messages(session_id) if client else []
                    live.apply_messages_payload(msgs)
                    _publish()
                except Exception:
                    pass

        poller = threading.Thread(target=_poll_loop, daemon=True)
        poller.start()

        # Async prompt so we can poll messages while running
        prompt_err: Optional[str] = None
        try:
            client.prompt_async(
                session_id,
                text=task_prompt,
                provider_id=pid,
                model_id=model_version,
                agent="build",
                system=system_prompt,
            )
        except Exception as async_exc:
            prompt_err = str(async_exc)
            try:
                client.prompt(
                    session_id,
                    text=task_prompt,
                    provider_id=pid,
                    model_id=model_version,
                    agent="build",
                    system=system_prompt,
                    timeout=float(timeout),
                )
                prompt_err = None
            except Exception as sync_exc:
                prompt_err = f"{async_exc}; fallback: {sync_exc}"
        if prompt_err:
            raise RuntimeError(f"OpenCode prompt failed: {prompt_err}")

        # Wait until session goes idle or timeout
        deadline = start + timeout
        idle_hits = 0
        while time.time() < deadline:
            try:
                msgs = client.list_messages(session_id)
                live.apply_messages_payload(msgs)
                _publish()

                # Surface model/provider errors immediately (don't wait full timeout)
                if live.error:
                    break

                # Heuristic: assistant finished if last assistant has completed time
                # or status endpoint says idle
                status_idle = False
                try:
                    r = client._client.get(
                        f"{client.base_url}/session/status",
                        headers=client._headers(),
                    )
                    if r.status_code == 200:
                        st = r.json()
                        s = st.get(session_id) if isinstance(st, dict) else None
                        if isinstance(s, dict) and s.get("type") == "idle":
                            status_idle = True
                        elif s == "idle":
                            status_idle = True
                except Exception:
                    pass

                if status_idle:
                    idle_hits += 1
                    if idle_hits >= 2:
                        break
                else:
                    idle_hits = 0

                # Also stop if we see FINISHED in last assistant text and no running tools
                last_thought = ""
                if live.steps:
                    last_thought = (live.steps[-1].get("thought") or "")
                if re.search(r"\bFINISHED\b", last_thought, re.I):
                    # brief wait for any trailing tools
                    time.sleep(1.5)
                    msgs = client.list_messages(session_id)
                    live.apply_messages_payload(msgs)
                    _publish()
                    break
            except Exception as exc:
                print(f"[opencode] poll error: {exc}")
            time.sleep(1.0)
        else:
            # timeout
            client.abort(session_id)
            if not live.error:
                if not live.steps:
                    live.error = (
                        f"Timeout after {timeout}s with 0 agent turns. "
                        f"Usually: invalid provider/model config, auth failure, or empty API balance. "
                        f"provider={provider} model={model_version} base={resolved_base or 'default'}"
                    )
                else:
                    live.error = f"Timeout after {timeout}s"
            live.status = "failed"

        stop_poll.set()
        msgs = client.list_messages(session_id)
        live.apply_messages_payload(msgs)
        duration = time.time() - start
        live.status = "failed" if live.error else "completed"
        _publish()

        # Convert to AgentResult for existing evaluate path
        rebuilt: list[AgentStep] = []
        for s in live.steps:
            rebuilt.append(
                AgentStep(
                    step_number=int(s.get("step") or len(rebuilt) + 1),
                    thought=s.get("thought") or "",
                    observation=s.get("observation") or "",
                    tool_calls=s.get("tool_calls") or [],
                    tokens_used=int(s.get("tokens") or 0),
                    duration_ms=float(s.get("duration_ms") or 0),
                    tools_completed=int(s.get("tools_completed") or 0),
                )
            )

        ok = not live.error and live.status != "failed"
        result = AgentResult(
            status=AgentStatus.COMPLETED if ok else AgentStatus.FAILED,
            steps=rebuilt,
            total_tokens=live.total_tokens,
            input_tokens=live.input_tokens,
            output_tokens=live.output_tokens,
            total_duration=duration,
            error=live.error,
            run_id=session_id,
        )
        return OfficialRunResult(
            status="success" if ok else "failed",
            agent_result=result,
            session_id=session_id,
            server_url=server.url if server else "",
            raw_messages=msgs,
        )

    except Exception as exc:
        stop_poll.set()
        live.error = str(exc)
        live.status = "failed"
        _publish()
        duration = time.time() - start
        return OfficialRunResult(
            status="failed",
            agent_result=AgentResult(
                status=AgentStatus.FAILED,
                steps=[],
                error=str(exc),
                total_duration=duration,
            ),
            session_id=session_id,
        )
    finally:
        stop_poll.set()
        if client:
            try:
                client.close()
            except Exception:
                pass
        if server:
            server.close()
