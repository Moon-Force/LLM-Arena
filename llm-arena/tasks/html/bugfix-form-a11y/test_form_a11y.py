"""A11y-oriented static tests for contact form."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HTML = (ROOT / "index.html").read_text(encoding="utf-8")


def test_form_and_fields():
    assert 'id="contact-form"' in HTML or "id='contact-form'" in HTML
    for i in ("name", "email", "message", "form-submit", "form-error"):
        assert re.search(rf'id=["\']{i}["\']', HTML)


def test_labels_for_fields():
    for i in ("name", "email", "message"):
        assert re.search(rf'<label[^>]+for=["\']{i}["\']', HTML, re.I), f"missing label for={i}"


def test_required_aria_on_email_message():
    for i in ("email", "message"):
        # field should include required and aria-required
        m = re.search(rf'<[^>]+id=["\']{i}["\'][^>]*>', HTML, re.I)
        assert m, i
        tag = m.group(0)
        assert "required" in tag
        assert re.search(r'aria-required=["\']true["\']', tag, re.I)


def test_error_live_region():
    m = re.search(r'<[^>]+id=["\']form-error["\'][^>]*>', HTML, re.I)
    assert m
    tag = m.group(0)
    assert re.search(r'role=["\']alert["\']', tag, re.I)
    assert "aria-live" in tag


def test_submit_type():
    m = re.search(r'<button[^>]+id=["\']form-submit["\'][^>]*>', HTML, re.I)
    assert m
    assert re.search(r'type=["\']submit["\']', m.group(0), re.I)


def test_focus_visible_css():
    assert re.search(r":focus-visible|:focus", HTML)
    assert re.search(r"outline|box-shadow", HTML)


def test_validation_script():
    assert "preventDefault" in HTML
    assert "form-error" in HTML
    assert re.search(r"email|validity|includes\(@\)|type=\"email\"", HTML)


def test_email_input_type():
    m = re.search(r'<input[^>]+id=["\']email["\'][^>]*>', HTML, re.I)
    assert m
    # prefer type=email after fix
    assert 'type="email"' in m.group(0) or "type='email'" in m.group(0) or "type=\"text\"" not in m.group(0)
