"""Structure + JS hook tests for kanban board task."""
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
        self.data_attrs: list[tuple[str, str]] = []
        self.texts: list[str] = []

    def handle_starttag(self, tag, attrs):
        ad = dict(attrs)
        if "id" in ad:
            self.ids.add(ad["id"])
        if "class" in ad:
            self.classes.extend(ad["class"].split())
        for k, v in ad.items():
            if k.startswith("data-") and v is not None:
                self.data_attrs.append((k, v))

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
    assert len(html) > 2500


def test_header():
    c = _load()
    assert "board-header" in c.ids
    assert "board-title" in c.ids
    assert "btn-add-card" in c.ids
    assert re.search(r"Sprint Board", " ".join(c.texts), re.I)


def test_board_and_columns():
    c = _load()
    assert "kanban-board" in c.ids
    assert c.classes.count("kanban-column") >= 4
    cols = {v for k, v in c.data_attrs if k == "data-column"}
    for name in ("backlog", "progress", "review", "done"):
        assert name in cols, f"missing data-column={name}"
    for i in ("col-backlog", "col-progress", "col-review", "col-done"):
        assert i in c.ids, f"missing {i}"


def test_column_chrome():
    c = _load()
    assert "column-header" in c.classes
    assert "column-title" in c.classes
    assert "column-count" in c.classes
    assert "column-cards" in c.classes


def test_cards_seed():
    c = _load()
    assert c.classes.count("kanban-card") >= 6
    assert "card-title" in c.classes
    assert "card-meta" in c.classes
    assert "card-priority" in c.classes or re.search(r"priority-(low|med|high)", _blob())
    assert "card-move-next" in c.classes
    card_ids = [v for k, v in c.data_attrs if k == "data-card-id"]
    assert len(card_ids) >= 6


def test_priority_values():
    blob = _blob()
    assert re.search(r"data-priority|priority-low|priority-med|priority-high|low|med|high", blob, re.I)


def test_new_card_form():
    c = _load()
    for i in ("new-card-form", "new-card-title", "new-card-assignee", "new-card-priority", "new-card-cancel", "new-card-submit"):
        assert i in c.ids, f"missing {i}"


def test_filter():
    c = _load()
    assert "filter-priority" in c.ids


def test_js_add_move_filter():
    blob = _blob()
    assert "btn-add-card" in blob
    assert "card-move-next" in blob
    assert "filter-priority" in blob
    assert re.search(r"addEventListener|onclick", blob, re.I)
    assert re.search(r"appendChild|append\(|insertAdjacentHTML|createElement", blob)


def test_count_update_logic():
    blob = _blob()
    assert "column-count" in blob
    # likely updates textContent/innerText or similar
    assert re.search(r"textContent|innerText|innerHTML|column-count", blob)


def test_substantial_js():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    scripts = re.findall(r"<script[^>]*>([\s\S]*?)</script>", html, re.I)
    js_files = [p.read_text(encoding="utf-8") for p in ROOT.glob("*.js")]
    code = "\n".join(scripts + js_files)
    assert len(code.strip()) > 250, "kanban needs non-trivial interaction JS"
