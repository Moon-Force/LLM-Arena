"""DOM structure tests for landing hero task (no browser required)."""
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
        self._buf = ""

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


def _load() -> Collector:
    html_path = ROOT / "index.html"
    assert html_path.exists(), "index.html must exist"
    c = Collector()
    c.feed(html_path.read_text(encoding="utf-8"))
    return c


def test_index_exists():
    assert (ROOT / "index.html").exists()


def test_has_nav_ids():
    c = _load()
    for i in ("nav-features", "nav-pricing", "nav-docs"):
        assert i in c.ids, f"missing id={i}"


def test_has_hero():
    c = _load()
    assert "hero" in c.ids
    assert "h1" in c.tags


def test_cta_primary():
    c = _load()
    assert "cta-primary" in c.ids
    blob = " ".join(c.texts)
    assert re.search(r"Get started|Start free|Try free", blob, re.I), "CTA text missing"


def test_features_grid():
    c = _load()
    assert "features-grid" in c.ids
    assert c.classes.count("feature-card") >= 3


def test_footer():
    c = _load()
    assert "site-footer" in c.ids


def test_logo_brand():
    blob = " ".join(_load().texts)
    assert "NovaDesk" in blob


def test_not_placeholder_only():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    assert "Complete the NovaDesk landing page" not in html or "hero" in html
    assert len(html) > 400
