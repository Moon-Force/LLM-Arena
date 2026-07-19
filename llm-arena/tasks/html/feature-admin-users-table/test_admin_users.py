"""Structure + interaction hook tests for admin users dashboard."""
from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent


class Collector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids: set[str] = set()
        self.classes: list[str] = []
        self.tags: list[str] = []
        self.texts: list[str] = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        ad = dict(attrs)
        if "id" in ad:
            self.ids.add(ad["id"])
        if "class" in ad:
            self.classes.extend(ad["class"].split())

    def handle_data(self, data):
        t = data.strip()
        if t:
            self.texts.append(t)


def _blob() -> str:
    files = list(ROOT.glob("*.html")) + list(ROOT.glob("*.js")) + list(ROOT.glob("*.css"))
    return "\n".join(p.read_text(encoding="utf-8") for p in files)


def _load() -> Collector:
    p = ROOT / "index.html"
    assert p.exists()
    c = Collector()
    c.feed(p.read_text(encoding="utf-8"))
    return c


def test_index_exists():
    assert (ROOT / "index.html").exists()


def test_not_scaffold():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    assert "Scaffold only" not in html
    assert "TODO: implement" not in html
    assert len(html) > 3000


def test_shell():
    c = _load()
    for i in ("app-shell", "sidebar", "main", "topbar", "page-title", "global-search", "user-menu"):
        assert i in c.ids, f"missing {i}"


def test_sidebar_nav():
    c = _load()
    for i in ("sidebar-brand", "nav-overview", "nav-users", "nav-billing", "nav-settings"):
        assert i in c.ids, f"missing {i}"
    assert "Nimbus" in " ".join(c.texts)
    assert "nav-active" in c.classes or "nav-active" in _blob()


def test_kpi_row():
    c = _load()
    assert "kpi-row" in c.ids
    assert c.classes.count("kpi-card") >= 3
    assert "kpi-label" in c.classes and "kpi-value" in c.classes


def test_toolbar():
    c = _load()
    for i in ("table-toolbar", "filter-role", "filter-status", "btn-invite"):
        assert i in c.ids, f"missing {i}"
    blob = " ".join(c.texts)
    assert re.search(r"Invite|Add user", blob, re.I)


def test_table_structure():
    c = _load()
    assert "users-table" in c.ids
    assert "users-tbody" in c.ids
    assert "table" in c.tags
    assert "thead" in c.tags
    assert c.classes.count("user-row") >= 8


def test_row_contract():
    c = _load()
    for cls in ("user-name", "user-email", "user-role", "user-status", "status-pill", "btn-edit"):
        assert cls in c.classes, f"missing class {cls}"
    assert "btn-more" in c.classes or "btn-delete" in c.classes
    blob = " ".join(c.texts)
    assert re.search(r"Admin|Member|Viewer", blob)
    assert re.search(r"Active|Invited|Suspended", blob)


def test_pagination():
    c = _load()
    for i in ("pagination", "page-prev", "page-next", "page-info"):
        assert i in c.ids, f"missing {i}"


def test_empty_and_modal():
    c = _load()
    for i in ("table-empty", "invite-modal", "invite-form", "invite-email", "invite-role", "invite-cancel", "invite-submit"):
        assert i in c.ids, f"missing {i}"


def test_filter_js_hooks():
    blob = _blob()
    assert "filter-role" in blob and "filter-status" in blob
    assert "global-search" in blob
    assert re.search(r"addEventListener|on(input|change|click)", blob, re.I)
    assert re.search(r"display|hidden|classList|filter", blob, re.I)


def test_modal_js_hooks():
    blob = _blob()
    assert "btn-invite" in blob and "invite-modal" in blob
    assert re.search(r"invite-cancel|invite-modal", blob)
    assert len(re.findall(r"<script|addEventListener", blob, re.I)) >= 1


def test_has_substantial_js():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    scripts = re.findall(r"<script[^>]*>([\s\S]*?)</script>", html, re.I)
    js_files = [p.read_text(encoding="utf-8") for p in ROOT.glob("*.js")]
    code = "\n".join(scripts + js_files)
    assert len(code.strip()) > 200, "admin interactions need non-trivial JS"
