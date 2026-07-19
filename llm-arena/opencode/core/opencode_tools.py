"""Official OpenCode built-in tools (anomalyco/opencode).

Source of truth for Arena permissions UI + frozen agent config.
@see https://opencode.ai/docs/tools
"""

from __future__ import annotations

from typing import Any

# Official built-in tools and Arena default permission.
# question stays deny so unattended arena runs never block on human input.
OPENCODE_TOOLS: list[dict[str, Any]] = [
    {
        "id": "bash",
        "name": "bash",
        "category": "shell",
        "description": "Execute shell commands in the project environment",
        "default": "allow",
    },
    {
        "id": "read",
        "name": "read",
        "category": "files",
        "description": "Read file contents (optional line ranges)",
        "default": "allow",
    },
    {
        "id": "write",
        "name": "write",
        "category": "files",
        "description": "Create or overwrite files",
        "default": "allow",
    },
    {
        "id": "edit",
        "name": "edit",
        "category": "files",
        "description": "Exact string replacement edits",
        "default": "allow",
    },
    {
        "id": "apply_patch",
        "name": "apply_patch",
        "category": "files",
        "description": "Apply multi-file patches / diffs",
        "default": "allow",
        "permission_key": "edit",  # controlled by edit permission in OpenCode
    },
    {
        "id": "glob",
        "name": "glob",
        "category": "search",
        "description": "Find files by glob pattern",
        "default": "allow",
    },
    {
        "id": "grep",
        "name": "grep",
        "category": "search",
        "description": "Search file contents with regex (ripgrep)",
        "default": "allow",
    },
    {
        "id": "list",
        "name": "list",
        "category": "search",
        "description": "List directory entries",
        "default": "allow",
    },
    {
        "id": "webfetch",
        "name": "webfetch",
        "category": "network",
        "description": "Fetch content from a URL",
        "default": "allow",
    },
    {
        "id": "websearch",
        "name": "websearch",
        "category": "network",
        "description": "Web search via Exa (requires OPENCODE_ENABLE_EXA)",
        "default": "allow",
        "requires_env": ["OPENCODE_ENABLE_EXA"],
    },
    {
        "id": "todowrite",
        "name": "todowrite",
        "category": "session",
        "description": "Create and update session todo lists",
        "default": "allow",
    },
    {
        "id": "skill",
        "name": "skill",
        "category": "session",
        "description": "Load a skill (SKILL.md) into the session",
        "default": "allow",
    },
    {
        "id": "lsp",
        "name": "lsp",
        "category": "codeintel",
        "description": "LSP code intelligence (experimental)",
        "default": "allow",
        "experimental": True,
    },
    {
        "id": "task",
        "name": "task",
        "category": "session",
        "description": "Spawn sub-agent tasks",
        "default": "allow",
    },
    {
        "id": "question",
        "name": "question",
        "category": "session",
        "description": "Ask the user a question (disabled for unattended arena)",
        "default": "deny",
        "arena_note": "Denied so fair matches never block on human input",
    },
]


def permission_map() -> dict[str, str]:
    """OpenCode permission object for opencode.json / OPENCODE_CONFIG_CONTENT."""
    perms: dict[str, str] = {}
    for t in OPENCODE_TOOLS:
        key = t.get("permission_key") or t["id"]
        # First write wins for shared keys like edit; prefer allow if any allows
        action = t.get("default") or "allow"
        if key not in perms or (perms[key] == "deny" and action == "allow"):
            perms[key] = action
    # Catch-all
    perms["*"] = "allow"
    # Explicit overrides for arena safety
    perms["question"] = "deny"
    perms["external_directory"] = "deny"
    return perms


def public_tools_payload() -> dict[str, Any]:
    """Payload for GET /api/v1/constraints (frontend)."""
    enabled = [t for t in OPENCODE_TOOLS if t.get("default") != "deny"]
    denied = [t for t in OPENCODE_TOOLS if t.get("default") == "deny"]
    return {
        "engine": "opencode-ai",
        "docs": "https://opencode.ai/docs/tools",
        "tools": OPENCODE_TOOLS,
        "permission": permission_map(),
        "enabled_count": len(enabled),
        "denied_count": len(denied),
        "enabled_ids": [t["id"] for t in enabled],
        "denied_ids": [t["id"] for t in denied],
        "note": (
            "All official OpenCode tools are enabled except question "
            "(unattended arena). websearch needs OPENCODE_ENABLE_EXA=1."
        ),
    }
