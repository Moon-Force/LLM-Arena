"""Evaluation tracks for fair multi-model arena.

Tracks only partition *what* is tested (task pool + leaderboard slice).
Within a track, single-variable principle still holds: only model identity
and API credentials may differ. Tools / system prompt / decoding stay frozen.
"""

from __future__ import annotations

from typing import Any, Optional

TRACK_IDS = (
    "algorithm",
    "bugfix",
    "feature",
    "frontend",
    "tooluse",
    "safety",
)

# Phase 1: only tracks with real tasks are enabled; others are beta placeholders.
TRACK_META: dict[str, dict[str, Any]] = {
    "algorithm": {
        "id": "algorithm",
        "order": 1,
        "enabled": True,
        "beta": False,
        "name": {"zh": "算法与函数", "en": "Algorithm"},
        "description": {
            "zh": "高难度函数/算法题（LiveCodeBench Hard / SciCode 风格），以单元测试通过为准。",
            "en": "Hard algorithm tasks (LiveCodeBench Hard / SciCode style), scored by unit tests.",
        },
        "default_tools_policy": "no_web",
        "metrics": ["pass_rate", "avg_tokens", "avg_duration", "stability"],
    },
    "bugfix": {
        "id": "bugfix",
        "order": 2,
        "enabled": True,
        "beta": False,
        "name": {"zh": "Bug 修复", "en": "Bugfix"},
        "description": {
            "zh": "在已有代码中定位并修复缺陷。",
            "en": "Locate and fix defects in existing code.",
        },
        "default_tools_policy": "full",
        "metrics": ["pass_rate", "hidden_pass_rate", "avg_tokens", "avg_duration", "stability"],
    },
    "feature": {
        "id": "feature",
        "order": 3,
        "enabled": True,
        "beta": False,
        "name": {"zh": "功能实现", "en": "Feature"},
        "description": {
            "zh": "从脚手架或空实现完成功能，通过功能测试。",
            "en": "Implement features from scaffold; scored by functional tests.",
        },
        "default_tools_policy": "full",
        "metrics": ["pass_rate", "hidden_pass_rate", "avg_tokens", "avg_duration", "stability"],
    },
    "frontend": {
        "id": "frontend",
        "order": 4,
        "enabled": True,
        "beta": False,
        "name": {"zh": "前端 / UI", "en": "Frontend / UI"},
        "description": {
            "zh": "页面结构、交互与可访问性（FrontendBench 风格）。",
            "en": "Layout, interaction, and a11y (FrontendBench-style).",
        },
        "default_tools_policy": "full",
        "metrics": ["pass_rate", "hidden_pass_rate", "avg_tokens", "avg_duration", "stability"],
    },
    "tooluse": {
        "id": "tooluse",
        "order": 5,
        "enabled": False,
        "beta": True,
        "name": {"zh": "Agent 工具", "en": "Tool use"},
        "description": {
            "zh": "多步工具链（bash / webfetch / websearch 等）。",
            "en": "Multi-step tool chains (bash / webfetch / websearch).",
        },
        "default_tools_policy": "full",
        "metrics": ["pass_rate", "avg_tokens", "avg_duration", "stability"],
    },
    "safety": {
        "id": "safety",
        "order": 6,
        "enabled": False,
        "beta": True,
        "name": {"zh": "安全", "en": "Safety"},
        "description": {
            "zh": "安全相关行为与危险模式检测（规划中）。",
            "en": "Safety behavior and dangerous-pattern checks (planned).",
        },
        "default_tools_policy": "full",
        "metrics": ["pass_rate", "stability"],
    },
}


def normalize_track(track: Optional[str]) -> Optional[str]:
    if track is None:
        return None
    t = str(track).strip().lower()
    if not t or t == "all":
        return "all" if t == "all" else None
    return t if t in TRACK_IDS else None


def infer_track(
    language: str = "",
    type_: str = "",
    explicit: Optional[str] = None,
) -> str:
    """Resolve track: explicit task field wins, else language/type heuristic."""
    if explicit:
        n = normalize_track(explicit)
        if n and n != "all":
            return n
    lang = (language or "").lower().strip()
    typ = (type_ or "").lower().strip()
    if lang in ("html", "css", "javascript", "typescript", "js", "ts", "htm"):
        return "frontend"
    if typ in ("algorithm", "algo", "function"):
        return "algorithm"
    if typ == "bugfix":
        return "bugfix"
    if typ == "feature":
        return "feature"
    return "feature"


def validate_task_track(task_track: str, requested: Optional[str]) -> str:
    """Ensure arena request track matches task. Returns the effective track."""
    effective = infer_track(explicit=task_track) if task_track else "feature"
    if not requested or requested == "all":
        return effective
    req = normalize_track(requested)
    if not req or req == "all":
        return effective
    if req != effective:
        raise ValueError(
            f"Task belongs to track={effective!r}, not {req!r}. "
            f"Pick a task from the selected track (single-variable: same track for all models)."
        )
    return effective


def list_public_tracks(task_counts: Optional[dict[str, int]] = None) -> list[dict[str, Any]]:
    """Public track list for GET /api/v1/tracks."""
    counts = task_counts or {}
    items = []
    for tid in sorted(TRACK_META.keys(), key=lambda x: TRACK_META[x]["order"]):
        meta = TRACK_META[tid]
        items.append(
            {
                **meta,
                "task_count": int(counts.get(tid, 0)),
            }
        )
    return items


def track_note() -> str:
    return (
        "Tracks partition the task pool and leaderboard only. "
        "Within a track, single-variable principle holds: only model_id/provider/version "
        "and API credentials may differ; tools, system prompt, and decoding are frozen."
    )
