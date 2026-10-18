"""Share-image renderer (Pillow, no headless browser).

The layouts follow the site's own palette: near-black navy, off-white type,
one accent colour. Every size uses the same blocks, scaled, so a card made for
X can be re-rendered for Instagram or a story without re-writing the copy.

The renderer measures before it draws: if a spec has more rows than the format
can hold, the least important row is dropped instead of overlapping the footer.
"""

from __future__ import annotations

import io
import os
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFilter, ImageFont

SIZES: dict[str, tuple[int, int]] = {
    "x": (1600, 900),
    "instagram": (1080, 1350),
    "story": (1080, 1920),
    "reddit": (1200, 1200),
    "og": (1200, 630),
}

#: Link previews need fewer numbers; stories can take five.
ROW_CAP = {"og": 3, "story": 5}

INK = (241, 245, 249)
MUTED = (148, 163, 184)
DIM = (100, 116, 139)
LINE = (30, 41, 59)
TOP = (8, 13, 24)
BOTTOM = (18, 29, 51)

KIND_LABELS = {
    "player": "Player profile",
    "comparison": "Head to head",
    "metric": "Metric of the day",
    "round_recap": "Round recap",
    "matchup": "Matchup",
}

_FONT_FILES = {
    False: ("segoeui.ttf", "arial.ttf", "DejaVuSans.ttf", "LiberationSans-Regular.ttf"),
    True: ("segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf"),
}

_FONT_DIRS = (
    os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"),
    os.path.expanduser("~/.fonts"),
    "/usr/share/fonts/truetype/dejavu",
    "/usr/share/fonts/truetype/liberation",
    "/System/Library/Fonts/Supplemental",
)


def _font_file(bold: bool) -> str | None:
    for directory in _FONT_DIRS:
        for name in _FONT_FILES[bold]:
            path = os.path.join(directory, name)
            if os.path.exists(path):
                return path
    return None


@lru_cache(maxsize=96)
def _font(size: int, bold: bool = False):
    path = _font_file(bold)
    if path:
        return ImageFont.truetype(path, size)
    try:
        return ImageFont.load_default(size)
    except TypeError:  # Pillow < 10.1
        return ImageFont.load_default()


def _rgb(value: str) -> tuple[int, int, int]:
    text = (value or "").lstrip("#")
    if len(text) != 6:
        return (52, 211, 153)
    try:
        return tuple(int(text[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
    except ValueError:
        return (52, 211, 153)


def _background(width: int, height: int, accent: tuple[int, int, int]) -> Image.Image:
    strip = Image.new("RGB", (1, height))
    for y in range(height):
        ratio = y / max(height - 1, 1)
        strip.putpixel((0, y), tuple(round(TOP[i] + (BOTTOM[i] - TOP[i]) * ratio) for i in range(3)))
    image = strip.resize((width, height)).convert("RGBA")

    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # One big soft glow, blurred: cheaper and smoother than stacked ellipses.
    centre_x, centre_y = width * 0.9, height * 0.14
    radius = int(width * 0.5)
    draw.ellipse(
        (centre_x - radius, centre_y - radius, centre_x + radius, centre_y + radius),
        fill=(*accent, 60),
    )
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=int(width * 0.14)))
    return Image.alpha_composite(image, overlay)


def _text_width(draw: ImageDraw.ImageDraw, text: str, font) -> float:
    return draw.textlength(text, font=font)


def _truncate(draw: ImageDraw.ImageDraw, text: str, font, max_width: float) -> str:
    text = " ".join((text or "").split())
    if _text_width(draw, text, font) <= max_width:
        return text
    while text and _text_width(draw, text + "…", font) > max_width:
        text = text[:-1]
    return text.rstrip() + "…" if text else ""


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: float, max_lines: int = 2) -> list[str]:
    words = " ".join((text or "").split()).split(" ")
    lines: list[str] = []
    current = ""
    for index, word in enumerate(words):
        trial = f"{current} {word}".strip()
        if current and _text_width(draw, trial, font) > max_width:
            lines.append(current)
            current = word
            if len(lines) == max_lines:
                remaining = " ".join(words[index:])
                lines[-1] = _truncate(draw, f"{lines[-1]} {remaining}", font, max_width)
                return lines
        else:
            current = trial
    if current:
        lines.append(current)
    return lines or [""]


def _advance(font) -> int:
    return int(getattr(font, "size", 16) * 1.28)


def _baseline_shift(big, small) -> int:
    try:
        return big.getmetrics()[0] - small.getmetrics()[0]
    except AttributeError:
        return 0


def _spaced(draw: ImageDraw.ImageDraw, xy: tuple[float, float], text: str, font, fill, spacing: float) -> None:
    x, y = xy
    for char in text:
        draw.text((x, y), char, font=font, fill=fill)
        x += _text_width(draw, char, font) + spacing


def _row_height(row: dict, columns: bool, f_note, f_value, small_gap: int) -> int:
    if columns:
        return int(_advance(f_note) * 1.05) + _advance(f_value) + small_gap
    height = _advance(f_value)
    if row.get("note"):
        height += int(_advance(f_note) * 0.95)
    return height + small_gap


def render_card(spec: dict, fmt: str = "x") -> bytes:
    """Render a spec dict to PNG bytes."""
    width, height = SIZES.get(fmt, SIZES["x"])
    accent = _rgb(spec.get("accent") or "#34d399")
    image = _background(width, height, accent)
    draw = ImageDraw.Draw(image)

    scale = min(width / 1600, height / 900)
    pad = int(width * 0.055)
    content_width = width - pad * 2

    f_eyebrow = _font(max(13, int(18 * scale)), bold=True)
    f_brand = _font(max(12, int(18 * scale)))
    f_title = _font(max(28, int(76 * scale)), bold=True)
    f_subtitle = _font(max(14, int(26 * scale)))
    f_headline = _font(max(40, int(140 * scale)), bold=True)
    f_head_label = _font(max(13, int(26 * scale)), bold=True)
    f_note = _font(max(12, int(20 * scale)))
    f_row = _font(max(13, int(27 * scale)))
    f_row_value = _font(max(15, int(34 * scale)), bold=True)
    f_footer = _font(max(12, int(18 * scale)))

    title_lines = _wrap(draw, spec.get("title", ""), f_title, content_width, max_lines=2)
    subtitle = _truncate(draw, spec.get("subtitle", ""), f_subtitle, content_width)
    columns = spec.get("columns") or []
    rows = list(spec.get("rows") or [])[: ROW_CAP.get(fmt, 5)]
    headline = spec.get("headline") or ""
    headline_label = spec.get("headline_label") or ""
    headline_note = spec.get("headline_note") or ""

    gap = int(18 * scale)
    small_gap = int(9 * scale)
    footer_h = _advance(f_footer)
    available = height - pad * 2 - footer_h - int(10 * scale)

    def measure() -> int:
        total = _advance(f_eyebrow) + gap
        total += len(title_lines) * _advance(f_title)
        if subtitle:
            total += int(_advance(f_subtitle) * 0.9)
        total += gap + max(2, int(3 * scale)) + gap
        if headline:
            total += _advance(f_headline) + int(5 * scale) + _advance(f_head_label)
            if headline_note:
                total += _advance(f_note)
            total += gap
        if columns:
            total += _advance(f_row_value) + small_gap
        total += sum(_row_height(row, columns, f_note, f_row_value, small_gap) for row in rows)
        return total

    block = measure()
    while rows and block > available:
        rows.pop()
        block = measure()

    free = available - block
    centre_ratio = {"story": 0.45, "instagram": 0.45, "reddit": 0.3, "x": 0.06, "og": 0.06}.get(fmt, 0.1)
    y = pad + (int(free * centre_ratio) if free > 0 else 0)

    # Header
    eyebrow = (spec.get("eyebrow") or KIND_LABELS.get(spec.get("kind"), "Catch & Stats")).upper()
    draw.rectangle((pad, y + int(4 * scale), pad + int(32 * scale), y + int(8 * scale)), fill=accent)
    _spaced(draw, (pad + int(44 * scale), y), eyebrow, f_eyebrow, accent, max(1.0, 2.0 * scale))
    brand = "catchandstats.com"
    draw.text((width - pad - _text_width(draw, brand, f_brand), y), brand, font=f_brand, fill=DIM)
    y += _advance(f_eyebrow) + gap

    for line in title_lines:
        draw.text((pad, y), line, font=f_title, fill=INK)
        y += _advance(f_title)

    if subtitle:
        draw.text((pad, y), subtitle, font=f_subtitle, fill=MUTED)
        y += int(_advance(f_subtitle) * 0.9)

    # Divider
    y += gap
    draw.line(((pad, y), (width - pad, y)), fill=LINE, width=max(1, int(1.5 * scale)))
    draw.line(((pad, y), (pad + int(80 * scale), y)), fill=accent, width=max(2, int(3 * scale)))
    y += max(2, int(3 * scale)) + gap

    if headline:
        draw.text((pad, y), headline, font=f_headline, fill=accent)
        y += _advance(f_headline) + int(5 * scale)
        draw.text((pad, y), headline_label.upper(), font=f_head_label, fill=INK)
        y += _advance(f_head_label)
        if headline_note:
            draw.text((pad, y), headline_note, font=f_note, fill=MUTED)
            y += _advance(f_note)
        y += gap

    if columns:
        left_label = _truncate(draw, columns[0], f_row_value, content_width / 2 - int(16 * scale))
        right_label = _truncate(draw, columns[1], f_row_value, content_width / 2 - int(16 * scale))
        draw.text((pad, y), left_label, font=f_row_value, fill=INK)
        draw.text(
            (width - pad - _text_width(draw, right_label, f_row_value), y),
            right_label,
            font=f_row_value,
            fill=INK,
        )
        y += _advance(f_row_value) + small_gap

        for index, row in enumerate(rows):
            if index:
                draw.line(((pad, y - int(4 * scale)), (width - pad, y - int(4 * scale))), fill=LINE, width=1)
            label = _truncate(draw, (row.get("label") or "").upper(), f_note, content_width * 0.5)
            draw.text(((width - _text_width(draw, label, f_note)) / 2, y), label, font=f_note, fill=DIM)
            y += int(_advance(f_note) * 1.05)

            left, right = row.get("left", "—"), row.get("right", "—")
            winner = row.get("winner")
            draw.text((pad, y), left, font=f_row_value, fill=accent if winner == "left" else INK)
            draw.text(
                (width - pad - _text_width(draw, right, f_row_value), y),
                right,
                font=f_row_value,
                fill=accent if winner == "right" else INK,
            )
            y += _advance(f_row_value) + small_gap
    else:
        for index, row in enumerate(rows):
            if index:
                draw.line(((pad, y - int(4 * scale)), (width - pad, y - int(4 * scale))), fill=LINE, width=1)
            value = row.get("value", "—")
            value_width = _text_width(draw, value, f_row_value)
            draw.text((width - pad - value_width, y), value, font=f_row_value, fill=INK)
            label = _truncate(
                draw,
                row.get("label", ""),
                f_row,
                content_width - value_width - int(24 * scale),
            )
            draw.text(
                (pad, y + _baseline_shift(f_row_value, f_row)),
                label,
                font=f_row,
                fill=MUTED,
            )
            if row.get("note"):
                draw.text(
                    (pad, y + int(_advance(f_row_value) * 0.92)),
                    _truncate(draw, row["note"], f_note, content_width - int(16 * scale)),
                    font=f_note,
                    fill=DIM,
                )
            y += _row_height(row, columns, f_note, f_row_value, small_gap)

    footer = spec.get("footer") or "catchandstats.com"
    footer_y = height - pad - footer_h
    dot = int(8 * scale)
    draw.ellipse((pad, footer_y + int(footer_h * 0.42), pad + dot, footer_y + int(footer_h * 0.42) + dot), fill=accent)
    draw.text((pad + int(18 * scale), footer_y), footer, font=f_footer, fill=DIM)

    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()
