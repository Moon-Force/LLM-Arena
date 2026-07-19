"""DOM / structure tests for hard SaaS landing task."""
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
        self.data_attrs: list[tuple[str, str]] = []
        self.texts: list[str] = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
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
    files = list(ROOT.glob("*.html")) + list(ROOT.glob("*.css")) + list(ROOT.glob("*.js"))
    return "\n".join(p.read_text(encoding="utf-8") for p in files)


def _load() -> Collector:
    html_path = ROOT / "index.html"
    assert html_path.exists(), "index.html must exist"
    c = Collector()
    c.feed(html_path.read_text(encoding="utf-8"))
    return c


def test_index_exists():
    assert (ROOT / "index.html").exists()


def test_not_scaffold():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    assert "Scaffold only" not in html
    assert "TODO: implement" not in html
    assert len(html) > 2500, "page seems too thin for multi-section landing"


def test_brand_orbitflow():
    assert "OrbitFlow" in " ".join(_load().texts)


def test_header_contract():
    c = _load()
    for i in ("site-header", "nav-product", "nav-pricing", "nav-customers", "nav-docs", "header-cta"):
        assert i in c.ids, f"missing {i}"


def test_hero_contract():
    c = _load()
    for i in ("hero", "hero-eyebrow", "hero-title", "hero-subtitle", "cta-primary", "cta-secondary"):
        assert i in c.ids, f"missing {i}"
    assert "h1" in c.tags
    blob = " ".join(c.texts)
    assert re.search(r"Start free|Get started|Try free|Book demo", blob, re.I)


def test_logo_cloud():
    c = _load()
    assert "logo-cloud" in c.ids
    assert c.classes.count("logo-item") >= 4


def test_features_dense():
    c = _load()
    assert "features" in c.ids or "features-grid" in c.ids
    assert "features-grid" in c.ids
    assert c.classes.count("feature-card") >= 6


def test_how_it_works():
    c = _load()
    assert "how-it-works" in c.ids
    assert c.classes.count("step-item") >= 3
    assert "step-number" in c.classes or "step-title" in c.classes


def test_testimonials():
    c = _load()
    assert "testimonials" in c.ids
    assert c.classes.count("testimonial-card") >= 3


def test_pricing_plans():
    c = _load()
    assert "pricing" in c.ids
    assert "billing-toggle" in c.ids
    assert c.classes.count("plan-card") >= 3
    plans = {v for k, v in c.data_attrs if k == "data-plan"}
    for p in ("starter", "pro", "enterprise"):
        assert p in plans, f"missing data-plan={p}"
    assert "plan-price" in c.classes
    assert "plan-cta" in c.classes


def test_faq():
    c = _load()
    assert "faq" in c.ids
    assert c.classes.count("faq-item") >= 4


def test_final_cta_footer():
    c = _load()
    assert "final-cta" in c.ids
    assert "final-cta-btn" in c.ids
    assert "site-footer" in c.ids
    assert c.classes.count("footer-col") >= 3


def test_css_variables_or_theme():
    blob = _blob()
    assert re.search(r"--[a-zA-Z][\w-]*\s*:", blob), "use CSS variables for theme tokens"


def test_interaction_hooks():
    blob = _blob()
    assert "billing-toggle" in blob
    assert re.search(r"addEventListener|onclick|details", blob, re.I)
