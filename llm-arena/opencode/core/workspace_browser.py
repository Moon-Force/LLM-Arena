"""Safe browser for per-agent workspaces (list / preview / delete)."""

from __future__ import annotations

import mimetypes
import re
import shutil
from pathlib import Path
from typing import Any, Optional

from .workspace import WorkspaceManager, resolve_in_workspace

TEXT_EXTENSIONS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".json", ".md", ".txt", ".css",
    ".html", ".htm", ".vue", ".svelte", ".yaml", ".yml", ".toml", ".ini",
    ".sh", ".bat", ".ps1", ".env", ".gitignore", ".sql", ".xml", ".svg",
    ".rs", ".go", ".java", ".c", ".cpp", ".h", ".cs", ".rb", ".php",
}

PREVIEWABLE_HTML = {".html", ".htm"}


def workspaces_root() -> Path:
    return WorkspaceManager().base_dir


def is_under_workspaces(path: Path) -> bool:
    try:
        path.resolve().relative_to(workspaces_root().resolve())
        return True
    except ValueError:
        return False


def delete_workspace(workspace_id: str) -> dict[str, Any]:
    """Delete one agent workspace folder (batch/folder) under data/workspaces.

    Security: path must resolve strictly under workspaces_root(); no escape.
    """
    root = workspaces_root().resolve()
    rel = workspace_id.replace("\\", "/").strip().strip("/")
    if not rel or ".." in rel.split("/"):
        raise ValueError("Invalid workspace id")
    target = (root / rel).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise PermissionError(f"Path escapes workspaces root: {workspace_id}") from exc
    if not target.exists():
        raise FileNotFoundError(f"Workspace not found: {workspace_id}")
    if not target.is_dir():
        raise ValueError(f"Not a workspace directory: {workspace_id}")
    # Only allow deleting leaf agent folders (…/batch/model__runid) or empty batches
    # Refuse deleting the workspaces root itself
    if target == root:
        raise PermissionError("Cannot delete workspaces root")
    shutil.rmtree(target)
    # Clean empty batch parent
    parent = target.parent
    if parent != root and parent.is_dir() and not any(parent.iterdir()):
        try:
            parent.rmdir()
        except OSError:
            pass
    return {"ok": True, "deleted": rel, "path": str(target)}


def delete_workspaces(workspace_ids: list[str]) -> dict[str, Any]:
    """Delete multiple workspaces; collect per-id results."""
    deleted: list[str] = []
    errors: list[dict[str, str]] = []
    for wid in workspace_ids:
        try:
            delete_workspace(wid)
            deleted.append(wid)
        except Exception as exc:
            errors.append({"id": wid, "error": str(exc)})
    return {"ok": len(errors) == 0, "deleted": deleted, "errors": errors}


def list_disk_workspaces(limit: int = 50) -> list[dict[str, Any]]:
    """Scan data/workspaces for agent folders (survives API restart)."""
    root = workspaces_root()
    if not root.exists():
        return []
    items: list[dict[str, Any]] = []
    for batch in sorted(root.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not batch.is_dir():
            continue
        for agent_dir in sorted(batch.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
            if not agent_dir.is_dir():
                continue
            src = agent_dir / "src"
            meta = agent_dir / "workspace.json"
            model_id = agent_dir.name.split("__")[0] if "__" in agent_dir.name else agent_dir.name
            run_token = agent_dir.name.split("__")[-1] if "__" in agent_dir.name else ""
            items.append({
                "id": f"{batch.name}/{agent_dir.name}",
                "batch_id": batch.name,
                "folder": agent_dir.name,
                "model_id": model_id,
                "run_token": run_token,
                "root": str(agent_dir.resolve()),
                "src": str(src.resolve()) if src.exists() else str(agent_dir.resolve()),
                "has_meta": meta.exists(),
                "mtime": agent_dir.stat().st_mtime,
            })
            if len(items) >= limit:
                return items
    return items


def _tree(base: Path, rel: Path = Path("."), max_depth: int = 6, depth: int = 0) -> list[dict]:
    if depth > max_depth:
        return []
    current = (base / rel).resolve()
    if not is_under_workspaces(current) and not str(current).startswith(str(base.resolve())):
        return []
    if not current.exists() or not current.is_dir():
        return []
    nodes = []
    try:
        entries = sorted(current.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    except PermissionError:
        return []
    for entry in entries:
        if entry.name.startswith(".") and entry.name not in {".env.example"}:
            # still show normal dotfiles that matter; skip caches
            if entry.name in {".pytest_cache", ".git", "__pycache__", "node_modules"}:
                continue
        rel_path = str((rel / entry.name).as_posix())
        if entry.is_dir():
            if entry.name in {"__pycache__", ".pytest_cache", "node_modules", ".git"}:
                continue
            nodes.append({
                "name": entry.name,
                "path": rel_path,
                "type": "directory",
                "children": _tree(base, rel / entry.name, max_depth, depth + 1),
            })
        else:
            nodes.append({
                "name": entry.name,
                "path": rel_path,
                "type": "file",
                "size": entry.stat().st_size,
                "ext": entry.suffix.lower(),
                "preview": entry.suffix.lower() in PREVIEWABLE_HTML,
                "text": entry.suffix.lower() in TEXT_EXTENSIONS or entry.suffix == "",
            })
    return nodes


def list_files(src_dir: str | Path) -> dict[str, Any]:
    base = Path(src_dir).resolve()
    if not base.exists():
        raise FileNotFoundError(f"Workspace not found: {base}")
    # Allow both workspaces root children and absolute agent src under data/workspaces
    root = workspaces_root().resolve()
    if root not in base.parents and base != root and not str(base).startswith(str(root)):
        # also allow if base is under root
        try:
            base.relative_to(root)
        except ValueError as exc:
            raise PermissionError("Path outside workspaces root") from exc
    return {
        "root": str(base),
        "files": _tree(base),
        "html_entrypoints": [
            n["path"]
            for n in _flatten(base)
            if n.get("ext") in PREVIEWABLE_HTML
        ],
    }


def _flatten(base: Path, rel: Path = Path(".")) -> list[dict]:
    out = []
    for node in _tree(base, rel):
        if node["type"] == "file":
            out.append(node)
        else:
            # children already nested; walk
            stack = list(node.get("children") or [])
            while stack:
                c = stack.pop()
                if c["type"] == "file":
                    out.append(c)
                else:
                    stack.extend(c.get("children") or [])
    return out


def read_file(src_dir: str | Path, rel_path: str, max_bytes: int = 512_000) -> dict[str, Any]:
    base = Path(src_dir).resolve()
    target = resolve_in_workspace(str(base), rel_path)
    if not target.exists() or not target.is_file():
        raise FileNotFoundError(rel_path)
    size = target.stat().st_size
    ext = target.suffix.lower()
    mime, _ = mimetypes.guess_type(str(target))
    mime = mime or "application/octet-stream"
    is_text = ext in TEXT_EXTENSIONS or mime.startswith("text/")
    if is_text:
        raw = target.read_bytes()[:max_bytes]
        try:
            content = raw.decode("utf-8")
        except UnicodeDecodeError:
            content = raw.decode("utf-8", errors="replace")
        return {
            "path": rel_path,
            "size": size,
            "mime": mime,
            "encoding": "utf-8",
            "content": content,
            "truncated": size > max_bytes,
            "preview": ext in PREVIEWABLE_HTML,
        }
    return {
        "path": rel_path,
        "size": size,
        "mime": mime,
        "encoding": None,
        "content": None,
        "binary": True,
        "preview": False,
        "message": "Binary file — download only",
    }


def find_src_for_run_workspace(workspace_path: Optional[str]) -> Optional[Path]:
    if not workspace_path:
        return None
    p = Path(workspace_path)
    if p.is_dir():
        return p.resolve()
    return None


def resolve_src_dir(workspace_id: str) -> Path:
    """Resolve `{batch}/{folder}` or `{batch}/{folder}/src` to the agent src dir."""
    root = workspaces_root() / workspace_id
    if not root.exists():
        # allow id already pointing at src
        alt = workspaces_root() / workspace_id.replace("\\", "/").rstrip("/")
        if not alt.exists():
            raise FileNotFoundError(workspace_id)
        root = alt
    src = root / "src" if (root / "src").is_dir() else root
    # safety: must stay under workspaces root
    src = src.resolve()
    src.relative_to(workspaces_root().resolve())
    return src


def pick_html_entrypoint(src: Path) -> str:
    files = list_files(src)
    entries: list[str] = files.get("html_entrypoints") or []
    for p in entries:
        if re.search(r"(^|/)index\.html?$", p, re.I):
            return p
    if entries:
        return entries[0]
    raise FileNotFoundError("No HTML entrypoint in workspace")


def prepare_html_for_preview(html: str, base_href: str) -> str:
    """Inject <base> so relative CSS/JS/images resolve against the preview URL.

    Using a real HTTP base is more accurate than srcdoc (which has no base and
    cannot load sibling styles.css / app.js).
    """
    if not base_href.endswith("/"):
        base_href = base_href + "/"
    # Don't double-inject
    if re.search(r"<base\s", html, re.I):
        return html
    base_tag = f'<base href="{base_href}">'
    if re.search(r"<head[^>]*>", html, re.I):
        return re.sub(r"(<head[^>]*>)", rf"\1\n    {base_tag}", html, count=1, flags=re.I)
    if re.search(r"<html[^>]*>", html, re.I):
        return re.sub(
            r"(<html[^>]*>)",
            rf'\1\n<head>\n    {base_tag}\n    <meta charset="utf-8">\n</head>',
            html,
            count=1,
            flags=re.I,
        )
    return f"<!DOCTYPE html><html><head>{base_tag}<meta charset=\"utf-8\"></head><body>{html}</body></html>"


def resolve_preview_file(src_dir: Path, asset_path: str) -> Path:
    """Resolve a preview asset path; default empty / to index.html."""
    rel = (asset_path or "").strip().lstrip("/")
    if not rel or rel.endswith("/"):
        rel = (rel or "") + "index.html"
    target = resolve_in_workspace(str(src_dir), rel)
    if not target.exists() or not target.is_file():
        raise FileNotFoundError(rel)
    return target
