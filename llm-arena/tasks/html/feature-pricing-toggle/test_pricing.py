"""Structure tests for pricing toggle page."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BLOB = "\n".join(p.read_text(encoding="utf-8") for p in ROOT.glob("*") if p.suffix in {".html", ".js", ".css"})


def test_pricing_section():
    assert re.search(r'id=["\']pricing["\']', BLOB)


def test_billing_toggle():
    assert re.search(r'id=["\']billing-toggle["\']', BLOB)


def test_three_plans():
    for plan in ("starter", "pro", "enterprise"):
        assert re.search(rf'data-plan=["\']{plan}["\']', BLOB), f"missing plan {plan}"
    assert BLOB.count("plan-card") >= 3


def test_plan_price_and_cta():
    assert "plan-price" in BLOB
    assert "plan-cta" in BLOB


def test_monthly_yearly_price_data():
    has_attrs = ("data-monthly" in BLOB and "data-yearly" in BLOB)
    has_spans = ("price-monthly" in BLOB and "price-yearly" in BLOB)
    assert has_attrs or has_spans, "need dual monthly/yearly price representation"


def test_toggle_switches_billing():
    assert re.search(r"billing-yearly|data-billing|yearly", BLOB)
    assert "addEventListener" in BLOB or "onclick" in BLOB


def test_not_stub_only():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    assert "Implement the pricing section" not in html or "plan-card" in html
    assert len(html) > 500
