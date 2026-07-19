"""Source-level tests for interactive todo app structure & JS hooks."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
files = list(ROOT.glob("*.html")) + list(ROOT.glob("*.js"))
BLOB = "\n".join(p.read_text(encoding="utf-8") for p in files)


def test_index_exists():
    assert (ROOT / "index.html").exists()


def test_core_ids():
    for i in ("todo-input", "todo-add", "todo-list", "todo-empty"):
        assert re.search(rf'id=["\']{i}["\']', BLOB), f"missing id {i}"


def test_item_class_contract():
    assert "todo-item" in BLOB
    assert "todo-complete" in BLOB
    assert "todo-remove" in BLOB


def test_done_class():
    assert re.search(r"\bdone\b", BLOB)


def test_add_listener():
    assert re.search(r"todo-add|getElementById\(\s*['\"]todo-add", BLOB)
    assert "addEventListener" in BLOB or "onclick" in BLOB


def test_creates_list_items():
    assert re.search(r"createElement\(\s*['\"]li['\"]\s*\)|innerHTML\s*\+|insertAdjacentHTML", BLOB)


def test_append_to_list():
    assert re.search(r"todo-list|getElementById\(\s*['\"]todo-list", BLOB)
    assert re.search(r"appendChild|append\(|insertAdjacentHTML|innerHTML", BLOB)


def test_empty_state_logic():
    # should reference todo-empty visibility or display
    assert "todo-empty" in BLOB
    assert re.search(r"display|hidden|classList|style", BLOB)


def test_not_empty_script():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    scripts = re.findall(r"<script[^>]*>([\s\S]*?)</script>", html, re.I)
    js_files = [p.read_text(encoding="utf-8") for p in ROOT.glob("*.js")]
    code = "\n".join(scripts + js_files)
    assert len(code.strip()) > 80, "interactive JS seems missing"
    assert "TODO: implement" not in code
