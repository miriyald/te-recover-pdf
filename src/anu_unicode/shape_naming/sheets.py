import logging
from collections.abc import Sequence
from pathlib import Path

import pymupdf
from PIL import Image, ImageDraw, ImageFont

from anu_unicode.shape_naming.atlas import EmbeddedFonts, GlyphStats, trim_to_ink

ROW_HEIGHT = 120
SHEET_WIDTH = 1600
TEXT_LEFT = 150
WORD_SIZE = 40
SHEET_DPI = 110
MAX_IMAGE_WIDTH = 360
GAP = 26
PADDING = 6
RED = (1, 0, 0)

logger = logging.getLogger(__name__)


def render_highlighted(fonts: EmbeddedFonts, text: str, target: str, size: float = WORD_SIZE) -> Image.Image | None:
    found = fonts.drawable(text)
    if found is None:
        return None
    font, form = found
    with pymupdf.open() as scratch:
        page = scratch.new_page(width=font.text_length(form, fontsize=size) + 2 * size, height=size * 2)
        plain, highlight = pymupdf.TextWriter(page.rect), pymupdf.TextWriter(page.rect, color=RED)
        x = size
        for char, drawn in zip(text, form, strict=True):
            (highlight if char == target else plain).append((x, size * 1.4), drawn, font=font, fontsize=size)
            x += font.text_length(drawn, fontsize=size)
        plain.write_text(page)
        highlight.write_text(page, color=RED)
        return trim_to_ink(page.get_pixmap(dpi=SHEET_DPI, alpha=False).pil_image(), PADDING)


def _row(sheet: Image.Image, top: int, number: int, stats: GlyphStats, fonts: EmbeddedFonts) -> None:
    draw = ImageDraw.Draw(sheet)
    label = ImageFont.load_default(15)
    draw.text((6, top + 8), f"#{number} U+{ord(stats.glyph):04X}", fill="black", font=label)
    draw.text((6, top + 30), f"n={stats.count} {'MARK' if stats.zero_width else ''}", fill="blue", font=label)
    x = TEXT_LEFT
    for text in (stats.glyph, *stats.words):
        image = render_highlighted(fonts, text, stats.glyph)
        if image is None:
            continue
        image.thumbnail((MAX_IMAGE_WIDTH, ROW_HEIGHT - 6))
        if x + image.width > SHEET_WIDTH:
            break
        sheet.paste(image, (x, top + 3))
        x += image.width + GAP
    draw.line((0, top + ROW_HEIGHT - 1, SHEET_WIDTH, top + ROW_HEIGHT - 1), fill="#bbbbbb")


def write_sheets(out: Path, stats: Sequence[GlyphStats], fonts: EmbeddedFonts, per_sheet: int) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    for index, start in enumerate(range(0, len(stats), per_sheet), 1):
        chunk = stats[start:start + per_sheet]
        sheet = Image.new("RGB", (SHEET_WIDTH, ROW_HEIGHT * len(chunk)), "white")
        for row, item in enumerate(chunk):
            _row(sheet, row * ROW_HEIGHT, start + row + 1, item, fonts)
        path = out / f"sheet-{index:02d}.png"
        sheet.save(path)
        paths.append(path)
    logger.info("contact sheets written", extra={"glyphs": len(stats), "sheets": len(paths), "path": str(out)})
    return paths
