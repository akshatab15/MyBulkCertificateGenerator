"""PDF certificate generation with ReportLab.

One predefined, fully vector "Modern Navy & Gold" template:

    ┌───────────────────────────────────────────────────────────┐
    │  ╔═══════════════════════════════════════════════════════╗  │
    │  ║                       ✦ (emblem)                      ║  │
    │  ║              CERTIFICATE OF APPRECIATION              ║  │
    │  ║        This certificate is proudly presented to       ║  │
    │  ║                  ── Recipient Name ──                 ║  │
    │  ║              for the successful completion of         ║  │
    │  ║                   Programme / Course                  ║  │
    │  ║        description, wrapped onto centred lines        ║  │
    │  ║   Date ─────────                     ───────── Signature ║ │
    │  ║  [QR]                                  Certificate ID  ║  │
    │  ╚═══════════════════════════════════════════════════════╝  │
    └───────────────────────────────────────────────────────────┘

Design notes
------------
* Clean white background with a refined double border (navy outer, gold
  inner) and subtle gold corner diamonds.  No side panel and no vertical
  filler lines, so the page reads as a polished certificate rather than a
  sparse poster.
* Deep navy ``#051a2a`` and elegant gold ``#c5a04a`` accents; the recipient
  name is the single largest gold element, giving a clear visual hierarchy.
* The certificate is landscape A4.  A real serif TrueType font (Times New
  Roman when available, otherwise Liberation Serif / Times on macOS) is
  embedded into the PDF.  Embedding a real font means every PDF viewer
  renders the text with exactly the metrics ReportLab used for centring and
  wrapping, so text can never drift and clip at the page edge.
* All variable text (title, recipient name, course, description, signature
  name, certificate id) is measured, wrapped and auto-fitted so that - even
  for very long values - it stays inside the content column and page
  boundaries.  ``plan_certificate_layout`` computes the full layout and is
  used both by the renderer and by the test-suite.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import date
from io import BytesIO
from pathlib import Path

import qrcode
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from .config import (
    DEFAULT_DESCRIPTION,
    DEFAULT_GOLD,
    DEFAULT_GOLD_LIGHT,
    DEFAULT_SIGNATURE,
    DEFAULT_THEME_COLOR,
    DEFAULT_TITLE,
)

PAGE_SIZE = landscape(A4)  # 297mm x 210mm (approx 842 x 595 pt)
PAGE_WIDTH, PAGE_HEIGHT = PAGE_SIZE

# --- "Modern Navy & Gold" geometry -------------------------------------------
FRAME_MARGIN = 28.0           # outer border inset from the page edge
CONTENT_MARGIN = 70.0         # left/right margin for centred content
DESCRIPTION_MAX_WIDTH = 620.0  # cap description line length for readability

_WHITE = HexColor("#ffffff")
_INK = HexColor("#142433")
_MUTED = HexColor("#6b6b6b")
_RULE = HexColor("#c5a04a")  # date / signature rules (gold)

_HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")

# ---------------------------------------------------------------------------
# Font handling ---------------------------------------------------------------
#
# ReportLab's built-in "Times-*" names are base-14 fonts that are *not*
# embedded.  Different PDF viewers substitute their own serif font for them,
# which can render noticeably wider than ReportLab's measurement, causing the
# centred text to overflow the right edge.  To make the certificate render
# identically everywhere we embed a real serif TrueType font and use its
# exact metrics for centring/wrapping.  If no system font is found we fall
# back to the built-in Times faces (metrics and drawing stay consistent, but
# the fallback has no cross-viewer guarantee).
# ---------------------------------------------------------------------------

_FONT_ROMAN = "Times-Roman"
_FONT_BOLD = "Times-Bold"
_FONT_ITALIC = "Times-Italic"
_FONT_BOLD_ITALIC = "Times-BoldItalic"

_FONT_CANDIDATES: tuple[tuple[str, str, str, str], ...] = (
    # Windows: Times New Roman
    (
        "C:/Windows/Fonts/times.ttf",
        "C:/Windows/Fonts/timesbd.ttf",
        "C:/Windows/Fonts/timesi.ttf",
        "C:/Windows/Fonts/timesbi.ttf",
    ),
    # macOS: Times New Roman
    (
        "/System/Library/Fonts/Supplemental/Times New Roman.ttf",
        "/System/Library/Fonts/Supplemental/Times New Roman Bold.ttf",
        "/System/Library/Fonts/Supplemental/Times New Roman Italic.ttf",
        "/System/Library/Fonts/Supplemental/Times New Roman Bold Italic.ttf",
    ),
    # Linux: Liberation Serif (metrically compatible with Times New Roman)
    (
        "/usr/share/fonts/truetype/liberation2/LiberationSerif-Regular.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSerif-Bold.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSerif-Italic.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSerif-BoldItalic.ttf",
    ),
)

_FONTS_READY = False


def _ensure_fonts() -> None:
    """Register an embedded serif font family once per process."""
    global _FONT_ROMAN, _FONT_BOLD, _FONT_ITALIC, _FONT_BOLD_ITALIC, _FONTS_READY
    if _FONTS_READY:
        return
    _FONTS_READY = True
    for normal, bold, italic, bold_italic in _FONT_CANDIDATES:
        paths = [Path(p) for p in (normal, bold, italic, bold_italic)]
        if all(p.is_file() for p in paths):
            pdfmetrics.registerFont(TTFont("CertTimesRoman", str(paths[0])))
            pdfmetrics.registerFont(TTFont("CertTimesBold", str(paths[1])))
            pdfmetrics.registerFont(TTFont("CertTimesItalic", str(paths[2])))
            pdfmetrics.registerFont(
                TTFont("CertTimesBoldItalic", str(paths[3]))
            )
            _FONT_ROMAN, _FONT_BOLD, _FONT_ITALIC, _FONT_BOLD_ITALIC = (
                "CertTimesRoman",
                "CertTimesBold",
                "CertTimesItalic",
                "CertTimesBoldItalic",
            )
            return
        is_windows_paths = [Path(p.replace("/", "\\")) for p in paths]
        if all(p.is_file() for p in is_windows_paths):
            pdfmetrics.registerFont(TTFont("CertTimesRoman", str(is_windows_paths[0])))
            pdfmetrics.registerFont(TTFont("CertTimesBold", str(is_windows_paths[1])))
            pdfmetrics.registerFont(TTFont("CertTimesItalic", str(is_windows_paths[2])))
            pdfmetrics.registerFont(
                TTFont("CertTimesBoldItalic", str(is_windows_paths[3]))
            )
            _FONT_ROMAN, _FONT_BOLD, _FONT_ITALIC, _FONT_BOLD_ITALIC = (
                "CertTimesRoman",
                "CertTimesBold",
                "CertTimesItalic",
                "CertTimesBoldItalic",
            )
            return


def _color(value: str | None, fallback: str) -> HexColor:
    """Return a HexColor for a valid ``#rrggbb`` string, else the fallback."""
    if isinstance(value, str) and _HEX_RE.match(value):
        return HexColor(value)
    return HexColor(fallback)


# ---------------------------------------------------------------------------
# Layout model ----------------------------------------------------------------
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PlacedText:
    """Single line of certificate text, ready to be drawn.

    Coordinates use ReportLab's convention (origin bottom-left, widths in
    points).  ``x0/y0/x1/y1`` is the approximate glyph bounding box, computed
    from the same font metrics used to draw, so it can be checked for fit.
    """

    key: str
    text: str
    centre: float
    baseline: float
    font: str
    size: float
    color: HexColor
    letter_space: float
    x0: float
    y0: float
    x1: float
    y1: float


@dataclass(frozen=True)
class PlacedRule:
    """A straight line segment on the certificate."""

    key: str
    x0: float
    y0: float
    x1: float
    y1: float
    color: HexColor
    line_width: float = 1.0


@dataclass(frozen=True)
class LayoutPlan:
    """Full, deterministic layout for one certificate.

    The renderer draws exactly what this plan describes, and the test-suite
    checks that every element stays inside the page / content column.
    """

    width: float
    height: float
    left: float
    right: float
    texts: tuple[PlacedText, ...]
    rules: tuple[PlacedRule, ...]
    qr: tuple[float, float, float, float] | None  # x0, y0, width, height


def _text_width(text: str, font: str, size: float, letter_space: float = 0.0) -> float:
    """Width of ``text`` including any per-glyph letter spacing."""
    if not text:
        return 0.0
    return stringWidth(text, font, size) + letter_space * len(text)


def _wrap(text: str | None, font: str, size: float, max_width: float) -> list[str]:
    """Greedy word-wrap, also splitting any single word wider than ``max_width``."""
    text = " ".join((text or "").split())
    if not text:
        return []
    lines: list[str] = []
    current = ""
    for word in text.split(" "):
        # Break words that are wider than the allowed line width.
        while word and stringWidth(word, font, size) > max_width:
            idx = len(word)
            while idx > 1 and stringWidth(word[:idx], font, size) > max_width:
                idx -= 1
            if current:
                lines.append(current)
                current = ""
            lines.append(word[:idx])
            word = word[idx:]
        if not word:
            continue
        trial = f"{current} {word}".strip()
        if stringWidth(trial, font, size) <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _fit_text(
    text: str | None,
    font: str,
    size_max: int,
    size_min: int,
    max_width: float,
    max_lines: int,
) -> tuple[float, list[str]]:
    """Pick the largest font size at which ``text`` wraps to <= max_lines lines."""
    text = text or ""
    for size in range(size_max, size_min - 1, -1):
        lines = _wrap(text, font, size, max_width)
        if lines and len(lines) <= max_lines:
            return size, lines
    size = size_min
    return size, _wrap(text, font, size, max_width)


def _fit_line(
    text: str | None, font: str, size_max: float, size_min: float, max_width: float
) -> float:
    """Pick the largest size at which ``text`` fits on a single line."""
    text = text or ""
    size = float(size_max)
    while size > size_min and stringWidth(text, font, size) > max_width:
        size -= 0.5
    return size


def _place(
    key: str,
    text: str,
    centre: float,
    baseline: float,
    font: str,
    size: float,
    color: HexColor,
    letter_space: float = 0.0,
) -> PlacedText:
    width = _text_width(text, font, size, letter_space)
    return PlacedText(
        key=key,
        text=text,
        centre=centre,
        baseline=baseline,
        font=font,
        size=size,
        color=color,
        letter_space=letter_space,
        x0=centre - width / 2,
        y0=baseline - size * 0.22,
        x1=centre + width / 2,
        y1=baseline + size * 0.80,
    )


def plan_certificate_layout(
    *,
    title: str | None,
    name: str,
    course: str,
    description: str | None,
    signature_name: str | None,
    certificate_id: str,
    issue_date: date | str | None = None,
    theme_color: str | None = None,
    width: float | None = None,
    height: float | None = None,
) -> LayoutPlan:
    """Compute the complete layout for one certificate (deterministic).

    Every dynamic string is wrapped and auto-shrunk so it fits inside the
    content column and the landscape A4 page.  The renderer draws exactly
    what this returns; tests assert the returned boxes stay on-page.
    """
    _ensure_fonts()
    width = width or PAGE_WIDTH
    height = height or PAGE_HEIGHT

    left = CONTENT_MARGIN
    right = width - CONTENT_MARGIN
    centre = width / 2
    content_w = right - left

    navy = _color(theme_color, DEFAULT_THEME_COLOR)
    gold = HexColor(DEFAULT_GOLD)
    gold_light = HexColor(DEFAULT_GOLD_LIGHT)

    texts: list[PlacedText] = []
    rules: list[PlacedRule] = []

    # ---- Heading (prominent, centred) ------------------------------------
    title_words = (title or DEFAULT_TITLE).strip().upper().split() or ["CERTIFICATE"]
    primary = title_words[0]
    secondary = " ".join(title_words[1:])

    primary_size = 40
    while (
        _text_width(primary, _FONT_BOLD, primary_size, 3.0) > content_w - 20
        and primary_size > 22
    ):
        primary_size -= 2
    texts.append(
        _place(
            "title-primary",
            primary,
            centre,
            height - 122,
            _FONT_BOLD,
            primary_size,
            navy,
            letter_space=3.0,
        )
    )

    if secondary:
        secondary_size = 21
        while (
            _text_width(secondary, _FONT_BOLD, secondary_size, 4.0) > content_w - 20
            and secondary_size > 11
        ):
            secondary_size -= 1
        texts.append(
            _place(
                "title-secondary",
                secondary,
                centre,
                height - 152,
                _FONT_BOLD,
                secondary_size,
                gold,
                letter_space=4.0,
            )
        )

    rules.append(
        PlacedRule(
            "title-divider",
            centre - 150,
            height - 168,
            centre + 150,
            height - 168,
            gold,
            1.4,
        )
    )

    # ---- Lead-in ---------------------------------------------------------
    texts.append(
        _place(
            "lead-in",
            "This certificate is proudly presented to",
            centre,
            height - 198,
            _FONT_ITALIC,
            12.5,
            _MUTED,
        )
    )

    # ---- Recipient name (largest gold element, <= 3 lines) ---------------
    name_size, name_lines = _fit_text(
        name, _FONT_BOLD_ITALIC, 34, 14, content_w - 40, 3
    )
    name_gap = name_size * 1.16
    name_first = height - 240
    for index, line in enumerate(name_lines):
        texts.append(
            _place(
                f"name-{index}",
                line,
                centre,
                name_first - name_gap * (len(name_lines) - 1) + name_gap * index,
                _FONT_BOLD_ITALIC,
                name_size,
                gold,
            )
        )
    name_last = name_first - name_gap * (len(name_lines) - 1)
    if name_lines:
        widest = max(_text_width(line, _FONT_BOLD_ITALIC, name_size) for line in name_lines)
        half = min(max(widest / 2 + 20, 100), content_w / 2 - 20)
        rules.append(
            PlacedRule(
                "name-underline",
                centre - half,
                name_last - 12,
                centre + half,
                name_last - 12,
                gold_light,
                1.0,
            )
        )

    # ---- "for the successful completion of" ------------------------------
    for_y = name_last - 36
    texts.append(
        _place(
            "for-line",
            "for the successful completion of",
            centre,
            for_y,
            _FONT_ROMAN,
            12.5,
            _INK,
        )
    )

    # ---- Programme / course (wraps to two lines if needed) ---------------
    course_size, course_lines = _fit_text(
        course, _FONT_BOLD, 19, 12, content_w - 60, 2
    )
    course_gap = course_size * 1.14
    course_first = for_y - 28
    for index, line in enumerate(course_lines):
        texts.append(
            _place(
                f"course-{index}",
                line,
                centre,
                course_first - course_gap * index,
                _FONT_BOLD,
                course_size,
                navy,
            )
        )
    course_last = course_first - course_gap * (len(course_lines) - 1)

    # ---- Description (wrapped, centred, space-bounded) -------------------
    desc_width = min(content_w - 20, DESCRIPTION_MAX_WIDTH)
    desc_floor = 138.0  # keeps clear of the date / signature block
    desc_start = max(course_last - 30, desc_floor + 14)
    description = description or DEFAULT_DESCRIPTION

    desc_size = 11.5
    final_lines: list[str] = []
    for size in (11.5, 11.0, 10.0, 9.0, 8.0):
        wrapped = _wrap(description, _FONT_ROMAN, size, desc_width)
        space_for = max(1, int((desc_start - desc_floor) // 13))
        if wrapped and len(wrapped) <= space_for:
            desc_size = size
            final_lines = wrapped
            break
    else:
        desc_size = 8.0
        final_lines = _wrap(description, _FONT_ROMAN, desc_size, desc_width)
    final_lines = final_lines[: max(1, int((desc_start - desc_floor) // 13))]

    for index, line in enumerate(final_lines):
        texts.append(
            _place(
                f"description-{index}",
                line,
                centre,
                desc_start - 13 * index,
                _FONT_ROMAN,
                desc_size,
                _MUTED,
            )
        )

    # ---- Date and signature (balanced bottom band) -----------------------
    rule_y = 92.0
    date_centre = left + 130
    signature_centre = right - 130
    block_half = 78.0

    date_value = issue_date.isoformat() if isinstance(issue_date, date) else str(issue_date)
    rules.append(
        PlacedRule(
            "date-rule",
            date_centre - block_half,
            rule_y,
            date_centre + block_half,
            rule_y,
            _RULE,
            0.9,
        )
    )
    rules.append(
        PlacedRule(
            "signature-rule",
            signature_centre - block_half,
            rule_y,
            signature_centre + block_half,
            rule_y,
            _RULE,
            0.9,
        )
    )

    texts.append(
        _place("date-label", "Date", date_centre, rule_y + 12, _FONT_ROMAN, 9.5, _MUTED)
    )
    texts.append(
        _place(
            "date-value",
            date_value,
            date_centre,
            rule_y - 16,
            _FONT_ROMAN,
            _fit_line(date_value, _FONT_ROMAN, 11, 7, block_half * 2),
            _MUTED,
        )
    )
    texts.append(
        _place(
            "signature-label",
            "Signature",
            signature_centre,
            rule_y + 12,
            _FONT_ROMAN,
            9.5,
            _MUTED,
        )
    )
    signature = signature_name or DEFAULT_SIGNATURE
    texts.append(
        _place(
            "signature-value",
            signature,
            signature_centre,
            rule_y - 16,
            _FONT_ROMAN,
            _fit_line(signature, _FONT_ROMAN, 11, 5, block_half * 2),
            _MUTED,
        )
    )

    # ---- Certificate id (small, centred, unobtrusive) --------------------
    cert_id_text = f"Certificate ID: {certificate_id}"
    texts.append(
        _place(
            "certificate-id",
            cert_id_text,
            centre,
            46,
            _FONT_ROMAN,
            _fit_line(cert_id_text, _FONT_ROMAN, 8.5, 6, content_w),
            _MUTED,
        )
    )

    # ---- QR card (clearly visible, bottom-left corner) -------------------
    qr_size = 66.0
    qr_x = FRAME_MARGIN + 14
    qr_y = FRAME_MARGIN + 14
    qr = (qr_x, qr_y, qr_size, qr_size)

    return LayoutPlan(
        width=width,
        height=height,
        left=left,
        right=right,
        texts=tuple(texts),
        rules=tuple(rules),
        qr=qr,
    )


# ---------------------------------------------------------------------------
# Drawing helpers -------------------------------------------------------------
# ---------------------------------------------------------------------------


def _make_qr_image(data: str) -> ImageReader:
    """Render ``data`` as a QR code and wrap it for ReportLab."""
    qr = qrcode.QRCode(box_size=6, border=1)
    qr.add_data(data)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return ImageReader(buffer)


def _draw_letter_spaced_center(
    pdf: canvas.Canvas,
    x_center: float,
    y: float,
    text: str,
    font: str,
    size: int,
    char_space: float,
    color: HexColor,
) -> None:
    """Draw centred text with modest letter spacing (ReportLab text object).

    ``Tc`` (character spacing) is part of the PDF graphics state and is *not*
    cleared by ``ET``.  ReportLab only emits ``Tc`` when it differs from its
    own canvas state (which stays 0), so without an explicit reset the extra
    spacing would leak into every text drawn afterwards and push the
    description off the right edge.  Resetting ``Tc`` to 0 at the end of the
    text object keeps the letter spacing local to the heading.
    """
    width = _text_width(text, font, size, char_space)
    obj = pdf.beginText()
    obj.setFont(font, size)
    obj.setCharSpace(char_space)
    obj.setFillColor(color)
    obj.setTextOrigin(x_center - width / 2, y)
    obj.textOut(text)
    obj.setCharSpace(0)
    pdf.drawText(obj)


def _draw_frame(
    pdf: canvas.Canvas,
    width: float,
    height: float,
    navy: HexColor,
    gold: HexColor,
    margin: float = FRAME_MARGIN,
) -> None:
    """Draw the white background and the navy-and-gold double border.

    A navy outer rule, a gold inner rule and four small gold corner diamonds
    frame the certificate cleanly without the extra filler lines of the old
    design.
    """
    # Clean white base.
    pdf.setFillColor(_WHITE)
    pdf.rect(0, 0, width, height, stroke=0, fill=1)

    # Outer navy border.
    pdf.setStrokeColor(navy)
    pdf.setLineWidth(3.0)
    pdf.rect(margin, margin, width - 2 * margin, height - 2 * margin, stroke=1, fill=0)

    # Inner gold border.
    inner = margin + 6.0
    pdf.setStrokeColor(gold)
    pdf.setLineWidth(1.0)
    pdf.rect(inner, inner, width - 2 * inner, height - 2 * inner, stroke=1, fill=0)

    # Small gold diamonds on the four inner corners.
    pdf.setFillColor(gold)
    d = 5.0
    for cx, cy in (
        (inner, inner),
        (width - inner, inner),
        (inner, height - inner),
        (width - inner, height - inner),
    ):
        diamond = pdf.beginPath()
        diamond.moveTo(cx, cy + d)
        diamond.lineTo(cx + d, cy)
        diamond.lineTo(cx, cy - d)
        diamond.lineTo(cx - d, cy)
        diamond.close()
        pdf.drawPath(diamond, stroke=0, fill=1)


def _draw_emblem(
    pdf: canvas.Canvas,
    cx: float,
    cy: float,
    radius: float,
    navy: HexColor,
    gold: HexColor,
) -> None:
    """Draw a small, subtle award star (gold ring + navy star)."""
    # Gold ring with a white centre.
    pdf.setFillColor(gold)
    pdf.circle(cx, cy, radius, stroke=0, fill=1)
    pdf.setFillColor(_WHITE)
    pdf.circle(cx, cy, radius - 2.5, stroke=0, fill=1)
    pdf.setStrokeColor(gold)
    pdf.setLineWidth(1.0)
    pdf.circle(cx, cy, radius - 2.5, stroke=1, fill=0)

    # Five-point navy star inside the ring.
    outer = (radius - 5.0) * 0.95
    inner = outer * 0.42
    points = []
    for i in range(10):
        angle = math.pi / 2 + i * math.pi / 5
        r = outer if i % 2 == 0 else inner
        points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    star = pdf.beginPath()
    star.moveTo(*points[0])
    for point in points[1:]:
        star.lineTo(*point)
    star.close()
    pdf.setFillColor(navy)
    pdf.drawPath(star, stroke=0, fill=1)


def generate_certificate(
    output_path: Path,
    *,
    name: str,
    course: str,
    issue_date: date,
    certificate_id: str,
    verify_url: str | None = None,
    title: str = DEFAULT_TITLE,
    description: str = DEFAULT_DESCRIPTION,
    theme_color: str = DEFAULT_THEME_COLOR,
    signature_name: str = DEFAULT_SIGNATURE,
    emblem: bool = True,
) -> Path:
    """Generate a single certificate PDF and return its path.

    All design fields are optional so existing callers keep working. Any
    exception is caught by the job processor, so one bad certificate cannot
    abort the batch.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    width, height = PAGE_SIZE
    navy = _color(theme_color, DEFAULT_THEME_COLOR)
    gold = HexColor(DEFAULT_GOLD)

    plan = plan_certificate_layout(
        title=title,
        name=name,
        course=course,
        description=description,
        signature_name=signature_name,
        certificate_id=certificate_id,
        issue_date=issue_date,
        theme_color=theme_color,
    )

    pdf = canvas.Canvas(str(output_path), pagesize=PAGE_SIZE)
    pdf.setTitle(f"Certificate {certificate_id}")

    _draw_frame(pdf, width, height, navy, gold)

    # Small, subtle emblem centred just inside the top border.
    if emblem:
        _draw_emblem(pdf, width / 2, height - 66, 17, navy, gold)

    # Draw every planned text element.
    for item in plan.texts:
        if item.letter_space:
            _draw_letter_spaced_center(
                pdf, item.centre, item.baseline, item.text,
                item.font, item.size, item.letter_space, item.color,
            )
        else:
            pdf.setFont(item.font, item.size)
            pdf.setFillColor(item.color)
            pdf.drawCentredString(item.centre, item.baseline, item.text)

    # Draw every planned rule / divider.
    for rule in plan.rules:
        pdf.setStrokeColor(rule.color)
        pdf.setLineWidth(rule.line_width)
        pdf.line(rule.x0, rule.y0, rule.x1, rule.y1)

    # Verification QR on a white card with a thin gold frame (bottom-left).
    if verify_url and plan.qr:
        qr_x, qr_y, qr_w, qr_h = plan.qr
        pad = 5
        pdf.setFillColor(_WHITE)
        pdf.setStrokeColor(gold)
        pdf.setLineWidth(0.8)
        pdf.roundRect(qr_x, qr_y, qr_w, qr_h, 5, stroke=1, fill=1)
        pdf.drawImage(
            _make_qr_image(verify_url),
            qr_x + pad,
            qr_y + pad,
            width=qr_w - 2 * pad,
            height=qr_h - 2 * pad,
            preserveAspectRatio=True,
            mask="auto",
        )

    pdf.showPage()
    pdf.save()
    return output_path