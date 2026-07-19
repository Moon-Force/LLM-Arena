"""Read/write LLM credentials between .env and the frontend.

Local-dev oriented: keys are stored in project .env (gitignored) and can be
synced to/from the UI model configuration.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Optional

# provider id -> env var names
PROVIDER_KEY_ENV = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "google": "GOOGLE_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "mimo": "MIMO_API_KEY",
    "custom": "OPENAI_API_KEY",
}

PROVIDER_BASE_ENV = {
    "openai": "OPENAI_BASE_URL",
    "anthropic": "ANTHROPIC_BASE_URL",
    "deepseek": "DEEPSEEK_BASE_URL",
    "mimo": "MIMO_BASE_URL",
    "custom": "OPENAI_BASE_URL",
}

# model id -> provider (for applying env keys onto known models)
DEFAULT_MODEL_PROVIDERS = {
    "claude-opus": "anthropic",
    "claude-sonnet": "anthropic",
    "gpt-4o": "openai",
    "gemini-pro": "google",
    "deepseek-v4-pro": "deepseek",
    "deepseek-v4-flash": "deepseek",
    "deepseek-chat": "deepseek",  # legacy (retiring)
    "mimo-v2.5-pro": "mimo",
}


def env_path() -> Path:
    # opencode/core/env_config.py -> llm-arena/.env
    return Path(__file__).resolve().parents[2] / ".env"


def _parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        key, _, val = s.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        values[key] = val
    return values


def read_provider_secrets() -> dict[str, Any]:
    """Load keys/base URLs from .env (+ process env as fallback)."""
    path = env_path()
    file_vals = _parse_env_file(path)

    def get(name: str) -> str:
        return (file_vals.get(name) or os.environ.get(name) or "").strip()

    providers: dict[str, dict[str, str]] = {}
    for provider, key_name in PROVIDER_KEY_ENV.items():
        api_key = get(key_name)
        base_name = PROVIDER_BASE_ENV.get(provider)
        base_url = get(base_name) if base_name else ""
        providers[provider] = {
            "api_key": api_key,
            "apiKey": api_key,
            "base_url": base_url,
            "baseUrl": base_url,
            "env_key": key_name,
            "has_key": bool(api_key),
        }

    models: dict[str, dict[str, str]] = {}
    for model_id, provider in DEFAULT_MODEL_PROVIDERS.items():
        p = providers.get(provider, {})
        models[model_id] = {
            "provider": provider,
            "api_key": p.get("api_key", ""),
            "apiKey": p.get("api_key", ""),
            "base_url": p.get("base_url", ""),
            "baseUrl": p.get("base_url", ""),
        }

    return {
        "env_path": str(path),
        "exists": path.exists(),
        "providers": providers,
        "models": models,
    }


def _upsert_env_line(lines: list[str], key: str, value: str) -> list[str]:
    """Set KEY=value in env lines; insert if missing (after LLM keys section if possible)."""
    pattern = re.compile(rf"^\s*{re.escape(key)}\s*=")
    out: list[str] = []
    found = False
    for line in lines:
        if pattern.match(line):
            out.append(f"{key}={value}")
            found = True
        else:
            out.append(line)
    if not found:
        # append near end before trailing empty lines
        insert_at = len(out)
        while insert_at > 0 and out[insert_at - 1].strip() == "":
            insert_at -= 1
        out.insert(insert_at, f"{key}={value}")
        if insert_at == len(out) - 1:
            out.append("")
    return out


def write_provider_secrets(
    updates: list[dict[str, Any]],
) -> dict[str, Any]:
    """Write provider secrets from frontend into .env.

    Each update item:
      { "provider": "deepseek", "api_key": "...", "base_url": "..." }
    Empty string clears the key (writes KEY=).
    None / omitted fields are skipped.
    """
    path = env_path()
    if path.exists():
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
    else:
        # bootstrap from example if present
        example = path.parent / ".env.example"
        if example.exists():
            lines = example.read_text(encoding="utf-8").splitlines()
        else:
            lines = [
                "# OpenCode Arena Environment Variables",
                "",
            ]

    written: list[str] = []
    for item in updates:
        provider = (item.get("provider") or "").strip().lower()
        if not provider or provider not in PROVIDER_KEY_ENV:
            continue
        key_name = PROVIDER_KEY_ENV[provider]
        if "api_key" in item or "apiKey" in item:
            val = item.get("api_key") if "api_key" in item else item.get("apiKey")
            if val is not None:
                lines = _upsert_env_line(lines, key_name, str(val).strip())
                written.append(key_name)
                os.environ[key_name] = str(val).strip()

        base_name = PROVIDER_BASE_ENV.get(provider)
        if base_name and ("base_url" in item or "baseUrl" in item):
            bval = item.get("base_url") if "base_url" in item else item.get("baseUrl")
            if bval is not None:
                lines = _upsert_env_line(lines, base_name, str(bval).strip())
                written.append(base_name)
                if str(bval).strip():
                    os.environ[base_name] = str(bval).strip()
                elif base_name in os.environ:
                    # keep process env if cleared file value optional
                    pass

    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return {
        "ok": True,
        "env_path": str(path),
        "updated_keys": written,
        "providers": read_provider_secrets()["providers"],
    }
