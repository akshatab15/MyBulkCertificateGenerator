"""Unit tests for the PDF generator (no HTTP layer involved)."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pytest
from reportlab import rl_config
from reportlab.pdfbase.pdfmetrics import stringWidth

from app.pdf_generator import (
    PAGE_HEIGHT,
    PAGE_WIDTH,
    generate_certificate,
    plan_certificate_layout,
)

# Matches the drawing operators ReportLab emits, in stream order:
#   "x Tc" (char spacing), "1 0 0 1 x y Tm" (text origin), "n Tf" (font size),
#   "(text) Tj" (show text).
_TEXT_OP_RE = re.compile(
    r"([-\d.]+)\s+Tc"
    r"|1 0 0 1 ([-\d.]+) ([-\d.]+) Tm"
    r"|([\d.]+)\s+Tf"
    r"|\((.*?)\)\s*Tj"
)


def _drawn_text_with_state(stream: str):
    """Yield ``(text, origin_x, size, active_char_spacing)`` for each ``Tj``."""
    char_space = 0.0
    origin_x = 0.0
    size = 0.0
    for line in stream.splitlines():
        for match in _TEXT_OP_RE.finditer(line):
            if match.group(1) is not None:
                char_space = float(match.group(1))
            elif match.group(2) is not None:
                origin_x = float(match.group(2))
            elif match.group(4) is not None:
                size = float(match.group(4))
            elif match.group(5) is not None:
                yield match.group(5), origin_x, size, char_space


def test_generate_certificate_creates_pdf(tmp_path: Path):
    output = tmp_path / "cert.pdf"
    result = generate_certificate(
        output,
        name="Alice Smith",
        course="Introduction to Python",
        issue_date=date(2026, 1, 15),
        certificate_id="CERT-ABCD1234",
        verify_url="http://testserver/certificates/CERT-ABCD1234/verify",
    )

    assert result == output
    assert output.exists()
    assert output.stat().st_size > 0
    # A valid PDF starts with the %PDF magic header.
    assert output.read_bytes()[:4] == b"%PDF"


def test_generate_certificate_creates_parent_dirs(tmp_path: Path):
    output = tmp_path / "nested" / "dir" / "cert.pdf"
    generate_certificate(
        output,
        name="Bob Jones",
        course="Data Structures",
        issue_date=date(2026, 2, 20),
        certificate_id="CERT-00000000",
    )
    assert output.exists()


def test_generate_certificate_without_qr(tmp_path: Path):
    output = tmp_path / "no_qr.pdf"
    generate_certificate(
        output,
        name="No QR",
        course="Testing",
        issue_date=date(2026, 1, 1),
        certificate_id="CERT-NOQR0000",
        verify_url=None,
    )
    assert output.read_bytes()[:4] == b"%PDF"


def test_page_is_landscape_a4(tmp_path: Path):
    output = tmp_path / "page.pdf"
    generate_certificate(
        output,
        name="Page Size",
        course="Testing",
        issue_date=date(2026, 1, 1),
        certificate_id="CERT-PAGE0000",
    )
    content = output.read_bytes().decode("latin-1")
    match = re.search(r"/MediaBox\s*\[\s*([\d.]+)\s*([\d.]+)\s*([\d.]+)\s*([\d.]+)\s*\]", content)
    assert match is not None, "generated PDF must declare a MediaBox"
    x0, y0, x1, y1 = (float(v) for v in match.groups())
    assert (x0, y0) == (0, 0)
    assert x1 == pytest.approx(PAGE_WIDTH, abs=1e-3)
    assert y1 == pytest.approx(PAGE_HEIGHT, abs=1e-3)
    assert x1 > y1, "page must be landscape (wider than tall)"


def test_qr_image_present_only_with_verify_url(tmp_path: Path):
    with_qr = tmp_path / "with_qr.pdf"
    generate_certificate(
        with_qr,
        name="QR Holder",
        course="Testing",
        issue_date=date(2026, 1, 1),
        certificate_id="CERT-QR000000",
        verify_url="http://testserver/certificates/CERT-QR000000/verify",
    )
    without_qr = tmp_path / "without_qr.pdf"
    generate_certificate(
        without_qr,
        name="QR Holder",
        course="Testing",
        issue_date=date(2026, 1, 1),
        certificate_id="CERT-QR000000",
        verify_url=None,
    )

    assert b"/Subtype /Image" in with_qr.read_bytes(), "a QR image must be embedded when a verify URL is given"
    assert b"/Subtype /Image" not in without_qr.read_bytes(), "no image should be embedded without a verify URL"


def test_plan_wraps_long_name_within_page():
    plan = plan_certificate_layout(
        title=None,
        name=(
            "Maximiliana Alexandrina Konstantina von Hohenzollern-"
            "Sigmaringen und Brandenburg-Preussen"
        ),
        course="Advanced Culinary Arts and Hospitality Management",
        description="A short description.",
        signature_name=None,
        certificate_id="CERT-LONGNAME",
        issue_date=date(2026, 5, 5),
    )

    name_lines = [t for t in plan.texts if t.key.startswith("name-")]
    assert len(name_lines) >= 2, "a very long name should wrap onto multiple lines"
    for text in plan.texts:
        assert text.x0 >= plan.left - 1e-6 and text.x1 <= plan.right + 1e-6
        assert text.x1 <= plan.width and text.y0 >= 0 and text.y1 <= plan.height
    for rule in plan.rules:
        assert rule.x0 >= -1e-6 and rule.x1 <= plan.width + 1e-6
        assert rule.y0 >= -1e-6 and rule.y1 <= plan.height + 1e-6


def test_plan_keeps_extreme_content_inside_content_column():
    plan = plan_certificate_layout(
        title="Certificate of Appreciation and Outstanding Achievement Award",
        name="Maximilian Konstantin von Hohenzollern-Sigmaringen III von Preussen",
        course=(
            "Advanced Distributed Systems Engineering for Scalable "
            "Cloud-Native Microservices Architectures 2026"
        ),
        description=(
            "Awarded in recognition of your outstanding participation, dedication and the "
            "successful completion of a rigorous multi-disciplinary programme that demanded "
            "sustained excellence across every module."
        ),
        signature_name=(
            "Dr. Josephine Fairweather-Evergreen, Chief Executive Officer"
        ),
        certificate_id="CERT-999999999999",
        issue_date=date(2026, 10, 10),
    )

    assert plan.width == PAGE_WIDTH
    assert plan.height == PAGE_HEIGHT
    for text in plan.texts:
        assert text.x1 <= plan.right + 1e-6, f"{text.key} overflows the content column ({text.x1:.1f} > {plan.right:.1f})"
        assert text.x0 >= plan.left - 1e-6, f"{text.key} starts left of the content column"
        assert text.x0 >= 0 and text.x1 <= plan.width, f"{text.key} outside the page width"
        assert text.y0 >= 0 and text.y1 <= plan.height, f"{text.key} outside the page height"
        assert len(text.text) > 0
    for rule in plan.rules:
        assert rule.x0 >= plan.left - 1e-6 and rule.x1 <= plan.right + 1e-6
        assert rule.y0 >= 0 and rule.y1 <= plan.height


def test_generate_certificate_embeds_a_real_serif_font(tmp_path: Path):
    output = tmp_path / "fonts.pdf"
    generate_certificate(
        output,
        name="Font Test",
        course="Typography",
        issue_date=date(2026, 1, 1),
        certificate_id="CERT-FONT0000",
    )
    content = output.read_bytes().decode("latin-1")
    assert "FontFile2" in content, "a TrueType font must be embedded (avoids viewer font substitution)"
    assert re.search(r"BaseFont\s*/AAAAAA\+", content) is not None


def test_long_description_wraps_inside_page_without_leaked_spacing(tmp_path: Path, monkeypatch):
    """Regression: a long description must wrap and stay inside the page.

    The heading uses letter spacing (``Tc``); ``Tc`` is PDF graphics state that
    is not cleared by ``ET``, so it must be reset or it leaks into every later
    line and pushes the description off the right edge (the original bug).
    """
    # Keep the content stream as plain text so the test can inspect the
    # drawing operators directly.
    monkeypatch.setattr(rl_config, "pageCompression", 0)

    long_description = (
        "In recognition of your outstanding participation, dedication and successful "
        "completion of the programme, demonstrating a deep understanding of the subject "
        "matter and a consistently excellent level of engagement throughout the course."
    )
    output = tmp_path / "long.pdf"
    generate_certificate(
        output,
        name="Akshata Bhoje",
        course="Python Programming",
        issue_date=date(2026, 10, 10),
        certificate_id="CERT-C8D13F0098",
        description=long_description,
    )

    plan = plan_certificate_layout(
        title=None,
        name="Akshata Bhoje",
        course="Python Programming",
        description=long_description,
        signature_name=None,
        certificate_id="CERT-C8D13F0098",
        issue_date=date(2026, 10, 10),
    )
    description_lines = {
        placed.text: (placed.font, placed.size)
        for placed in plan.texts
        if placed.key.startswith("description")
    }
    assert len(description_lines) >= 2, "the long description should wrap onto multiple lines"

    stream = output.read_bytes().decode("latin-1")
    seen = 0
    for text, origin_x, size, char_space in _drawn_text_with_state(stream):
        if text not in description_lines:
            continue
        seen += 1
        font, _ = description_lines[text]
        rendered_width = stringWidth(text, font, size) + char_space * len(text)
        right_edge = origin_x + rendered_width
        assert char_space == 0, f"letter spacing leaked into the description ({char_space})"
        assert right_edge <= plan.right + 0.5, (
            f"description line {text!r} ends at {right_edge:.1f}pt, past the "
            f"content column ({plan.right:.1f}pt)"
        )
        assert origin_x >= plan.left - 0.5
    assert seen == len(description_lines)
