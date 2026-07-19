"""Serialize OpenCode agent results for the API / frontend.

Conversation shape mirrors anomalyco/opencode Session.Message:
  - user / assistant / system messages
  - assistant content parts: text | reasoning | tool
  - tool state: pending | running | completed | error

See: https://github.com/anomalyco/opencode/blob/dev/packages/schema/src/session-message.ts
"""

from __future__ import annotations

import json
from typing import Any, Optional


def serialize_agent_steps(agent_result: Any) -> list[dict]:
    steps_out: list[dict] = []
    steps = getattr(agent_result, "steps", None) or []
    for s in steps:
        tool_calls = getattr(s, "tool_calls", None) or []
        tools = []
        for tc in tool_calls:
            if isinstance(tc, dict):
                tools.append(
                    {
                        "name": tc.get("name"),
                        "arguments": _truncate_args(tc.get("arguments") or tc.get("args") or {}),
                    }
                )
        thought = getattr(s, "thought", "") or ""
        obs = getattr(s, "observation", "") or ""
        tools_done = getattr(s, "tools_completed", None)
        if tools_done is None:
            tools_done = _count_obs_tools(obs) if obs else (len(tools) if thought else 0)
        steps_out.append(
            {
                "step": getattr(s, "step_number", len(steps_out) + 1),
                "thought": thought[:20000],
                "observation": obs[:20000],
                "tool_calls": tools,
                "tokens": getattr(s, "tokens_used", 0) or 0,
                "duration_ms": getattr(s, "duration_ms", 0) or 0,
                "tools_completed": int(tools_done or 0),
            }
        )
    return steps_out


def steps_to_messages(
    steps: list[dict],
    *,
    task_prompt: str = "",
    model_id: str = "",
    status: str = "",
    error: Optional[str] = None,
) -> list[dict]:
    """Convert ReAct steps into an OpenCode-style chat message list.

    OpenCode stores a linear conversation of messages, each with typed
    content parts (text / reasoning / tool). Our agent loop is step-based;
    this adapter unfolds steps into the same dialogue timeline for the UI.
    """
    messages: list[dict] = []
    msg_i = 0

    def _mid(prefix: str = "msg") -> str:
        nonlocal msg_i
        msg_i += 1
        return f"{prefix}_{msg_i:04d}"

    if task_prompt:
        messages.append(
            {
                "id": _mid(),
                "type": "user",
                "role": "user",
                "text": task_prompt[:16000],
            }
        )

    # Split multi-tool observation lines "name: result" back onto tools when possible
    n_steps = len(steps)
    is_live = str(status).lower() in ("running", "pending", "thinking", "acting", "")

    for si, s in enumerate(steps):
        step_no = s.get("step", 0)
        thought = (s.get("thought") or "").strip()
        tools = s.get("tool_calls") or []
        obs = (s.get("observation") or "").strip()
        tokens = s.get("tokens") or 0
        duration_ms = s.get("duration_ms") or 0
        is_last = si == n_steps - 1
        completed_tool_count = int(s.get("tools_completed") or 0)
        if not completed_tool_count and obs:
            completed_tool_count = _count_obs_tools(obs)
        # Live incomplete turn: waiting on model or still running tools
        step_incomplete = is_live and is_last and (
            not thought or (tools and completed_tool_count < len(tools))
        )

        # Official UI shows prose separately from tool parts — strip fences
        clean_text = _strip_tool_and_code_fences(thought) if tools else thought

        content: list[dict] = []
        if clean_text.strip():
            content.append(
                {
                    "type": "text",
                    "id": f"text_{step_no}",
                    "text": clean_text.strip()[:20000],
                }
            )
        elif step_incomplete and not tools:
            # Empty seed step while waiting on model — show as reasoning placeholder
            content.append(
                {
                    "type": "reasoning",
                    "id": f"think_{step_no}",
                    "text": f"Thinking (turn {step_no})… waiting for model response",
                }
            )

        # Map each tool call; attach observation chunk if we can parse per-tool lines
        # Progressive: first N tools (by tools_completed) have results in observation order
        obs_segments = _split_obs_by_tools(obs, [((tc.get("name") if isinstance(tc, dict) else None) or "tool") for tc in tools]) if tools else []

        for ti, tc in enumerate(tools):
            name = (tc.get("name") if isinstance(tc, dict) else None) or "tool"
            args = (tc.get("arguments") if isinstance(tc, dict) else {}) or {}
            output_text = obs_segments[ti] if ti < len(obs_segments) else ""
            # Progressive: tools before completed_tool_count are done; current is running
            if ti < completed_tool_count:
                tool_status = "completed"
            elif step_incomplete and ti == completed_tool_count:
                tool_status = "running"
            elif step_incomplete and ti > completed_tool_count:
                tool_status = "pending"
            else:
                tool_status = "completed"
            # Official BasicTool uses title "Called {tool}" + subtitle from path/query
            subtitle = _tool_subtitle(name, args if isinstance(args, dict) else {})
            title = f"Called {name}" if tool_status == "completed" else (
                f"Running {name}…" if tool_status == "running" else f"Queued {name}"
            )
            content.append(
                {
                    "type": "tool",
                    "id": f"tool_{step_no}_{ti}",
                    "name": name,
                    "title": title,
                    "subtitle": subtitle if tool_status == "completed" else "",
                    "state": {
                        "status": tool_status,
                        "input": args,
                        "output": (output_text or "")[:12000],
                    },
                }
            )

        # Observation with no tools still shown as system-ish tool result bubble
        if obs and not tools:
            content.append(
                {
                    "type": "tool",
                    "id": f"tool_{step_no}_obs",
                    "name": "observation",
                    "title": "Called observation",
                    "state": {
                        "status": "completed",
                        "input": {},
                        "output": obs[:12000],
                    },
                }
            )

        if content:
            messages.append(
                {
                    "id": _mid(),
                    "type": "assistant",
                    "role": "assistant",
                    "agent": "opencode",
                    "model": model_id or None,
                    "step": step_no,
                    "tokens": tokens,
                    "duration_ms": duration_ms,
                    "content": content,
                }
            )

    if error:
        messages.append(
            {
                "id": _mid(),
                "type": "system",
                "role": "system",
                "text": f"Error: {error}",
            }
        )
    elif status in ("completed", "success", "COMPLETED"):
        messages.append(
            {
                "id": _mid(),
                "type": "system",
                "role": "system",
                "text": "Session complete",
            }
        )

    return messages


def serialize_conversation(
    agent_result: Any,
    *,
    task_prompt: str = "",
    model_id: str = "",
) -> list[dict]:
    steps = serialize_agent_steps(agent_result)
    status = getattr(agent_result, "status", None)
    status_s = getattr(status, "value", status) if status is not None else ""
    err = getattr(agent_result, "error", None)
    mid = model_id or getattr(agent_result, "model_id", "") or ""
    return steps_to_messages(
        steps,
        task_prompt=task_prompt,
        model_id=mid,
        status=str(status_s or ""),
        error=err,
    )


def format_agent_log(agent_result: Any, code_diff: str = "") -> str:
    """Human-readable OpenCode dialogue transcript (chat-style)."""
    lines: list[str] = []
    status = getattr(agent_result, "status", None)
    status_s = getattr(status, "value", status) if status is not None else ""
    lines.append(
        f"[OpenCode session] status={status_s} "
        f"tokens={getattr(agent_result, 'total_tokens', 0)} "
        f"in={getattr(agent_result, 'input_tokens', 0)} "
        f"out={getattr(agent_result, 'output_tokens', 0)}"
    )
    err = getattr(agent_result, "error", None)
    if err:
        lines.append(f"[system] error: {err}")

    for msg in serialize_conversation(agent_result):
        mtype = msg.get("type") or msg.get("role")
        if mtype == "user":
            lines.append("\n── user ──")
            lines.append(str(msg.get("text") or "")[:12000])
        elif mtype == "system":
            lines.append(f"\n── system ──\n{msg.get('text')}")
        elif mtype == "assistant":
            step = msg.get("step")
            meta = f"step {step}" if step else "assistant"
            lines.append(f"\n── assistant ({meta}) ──")
            for part in msg.get("content") or []:
                ptype = part.get("type")
                if ptype == "text":
                    lines.append(part.get("text") or "")
                elif ptype == "reasoning":
                    lines.append(f"[reasoning]\n{part.get('text') or ''}")
                elif ptype == "tool":
                    st = part.get("state") or {}
                    lines.append(f"[tool:{part.get('name')}] status={st.get('status')}")
                    if st.get("input"):
                        lines.append(f"  input: {json.dumps(st.get('input'), ensure_ascii=False)[:800]}")
                    if st.get("output"):
                        lines.append(f"  output: {str(st.get('output'))[:2000]}")
    if code_diff:
        lines.append("\n── container stdout ──")
        lines.append(code_diff[:12000])
    return "\n".join(lines)


def load_transcript_from_workspace(workspace_path: str) -> tuple[list, str, int, float]:
    """Load steps/log written by the container agent into the mounted workspace."""
    from pathlib import Path

    p = Path(workspace_path) / ".opencode" / "transcript.json"
    if not p.exists():
        return [], "", 0, 0.0
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return [], "", 0, 0.0
    steps = data.get("steps") or []
    log = data.get("agent_log") or ""
    tokens = int(data.get("tokens") or 0)
    duration = float(data.get("duration") or 0)
    return steps, log, tokens, duration


def _strip_tool_and_code_fences(text: str) -> str:
    """Remove ```tool / ```html fences so dialogue shows clean prose (OpenCode-style)."""
    import re

    if not text:
        return ""
    # Drop fenced blocks that become tool parts
    cleaned = re.sub(
        r"```(?:tool|html|htm|css|js|javascript|ts|typescript|python|py|json)[^\n]*\n[\s\S]*?```",
        "",
        text,
        flags=re.IGNORECASE,
    )
    # Collapse excess blank lines
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _count_obs_tools(obs: str) -> int:
    """Count completed tool results in observation text (lines like 'name: result')."""
    if not obs or not obs.strip():
        return 0
    n = 0
    for line in obs.split("\n"):
        if ": " in line and not line.startswith(" "):
            n += 1
    return n


def _split_obs_by_tools(obs: str, tool_names: list[str]) -> list[str]:
    """Split observation into per-tool segments (joined as 'name: result')."""
    if not obs:
        return [""] * len(tool_names)
    if len(tool_names) == 1:
        # Single tool: whole observation after optional "name: " prefix
        name = tool_names[0]
        prefix = f"{name}: "
        if obs.startswith(prefix):
            return [obs[len(prefix):]]
        return [obs]
    # Multi-tool: split on lines that start a new "name: " for known tools
    segments: list[str] = []
    current: list[str] = []
    name_set = set(tool_names)
    for line in obs.split("\n"):
        matched = None
        for name in name_set:
            if line.startswith(f"{name}: "):
                matched = name
                break
        if matched is not None:
            if current or segments:
                segments.append("\n".join(current))
                current = []
            current.append(line[len(matched) + 2 :])  # strip "name: "
        else:
            current.append(line)
    if current or len(segments) < len(tool_names):
        segments.append("\n".join(current))
    # Pad / trim to tool count
    while len(segments) < len(tool_names):
        segments.append("")
    return segments[: len(tool_names)]


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
