"""Static + source-level checks for mobile navbar fix."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HTML = (ROOT / "index.html").read_text(encoding="utf-8")


def test_required_ids():
    for i in ("brand", "menu-toggle", "nav-links"):
        assert f'id="{i}"' in HTML or f"id='{i}'" in HTML


def test_nav_link_labels():
    for label in ("Home", "Product", "Contact"):
        assert label in HTML


def test_media_query_present():
    assert re.search(r"@media[^{]*max-width:\s*768px", HTML, re.I)


def test_menu_open_style():
    # body.menu-open or .menu-open should control nav visibility
    assert "menu-open" in HTML


def test_toggle_script():
    assert re.search(r"menu-toggle|getElementById\(\s*['\"]menu-toggle", HTML)
    assert "classList" in HTML or "className" in HTML
    assert "menu-open" in HTML.split("<script")[-1] if "<script" in HTML else "menu-open" in HTML


def test_hamburger_shown_on_mobile_css():
    # In mobile media query, menu-toggle should be display not none
    mq = re.search(r"@media[^{]*max-width:\s*768px\s*\{([\s\S]*?)\}(?:\s*@media|\s*$|\s*<\/style>)", HTML, re.I)
    assert mq, "missing max-width 768 media block"
    block = mq.group(1)
    # either #menu-toggle { display: block/flex } or similar
    assert "menu-toggle" in block or "menu-toggle" in HTML
    assert re.search(r"#menu-toggle[^{]*\{[^}]*display:\s*(block|flex|inline-block)", HTML, re.I | re.S)


def test_not_trivial_console_only():
    script = HTML.split("<script")[-1] if "<script" in HTML else ""
    assert "menu-open" in script or "classList.toggle" in HTML
