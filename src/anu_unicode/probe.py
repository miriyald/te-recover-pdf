import logging
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

import pymupdf
from PIL import Image

from anu_unicode.glyphs import ZERO_WIDTH, font_family, page_lines
from anu_unicode.profile import FontProfile

NON_TELUGU_MARKERS = ("times", "arial", "helvetica", "courier", "symbol", "zapf", "dingbat", "calibri", "verdana", "cambria", "futura")
INK_THRESHOLD = 128
RENDER_DPI = 200
MEASURE_SIZE = 40
MARGIN = 0.05
PERCENTILE = 0.99
SAMPLE_PAGES = 10

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FontUsage:
    family: str
    pages: int
    glyphs: int


@dataclass(frozen=True)
class ProbeResult:
    fonts: list[FontUsage]
    profile: FontProfile
    zero_width: Counter[str]


def candidate_families(families: Iterable[str]) -> frozenset[str]:
    return frozenset(family for family in families if not any(marker in family.lower() for marker in NON_TELUGU_MARKERS))


def percentile(values: Sequence[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(fraction * len(ordered)))]


def ink_extent(image: Image.Image, baseline_px: float, size_px: float) -> tuple[float, float] | None:
    mask = image.convert("L").point(lambda value: 255 if value < INK_THRESHOLD else 0)
    box = mask.getbbox()
    if box is None:
        return None
    return (baseline_px - box[1]) / size_px, (box[3] - baseline_px) / size_px


def _family_xrefs(document: pymupdf.Document) -> tuple[Counter[str], dict[str, int]]:
    pages: Counter[str] = Counter()
    xrefs: dict[str, int] = {}
    for page in document:
        for font in page.get_fonts():
            family = font_family(font[3])
            pages[family] += 1
            xrefs.setdefault(family, font[0])
    return pages, xrefs


def _load_font(document: pymupdf.Document, xref: int) -> pymupdf.Font | None:
    buffer = document.extract_font(xref)[3]
    return pymupdf.Font(fontbuffer=buffer) if buffer else None


def font_usage(document: pymupdf.Document) -> list[FontUsage]:
    pages, xrefs = _family_xrefs(document)
    loaded = {family: _load_font(document, xref) for family, xref in xrefs.items()}
    return [FontUsage(family, count, int(font.glyph_count) if font else 0) for family, count in pages.most_common()
            for font in [loaded[family]]]


def glyph_extent(font: pymupdf.Font, char: str) -> tuple[float, float] | None:
    scale = RENDER_DPI / 72
    with pymupdf.open() as scratch:
        page = scratch.new_page(width=MEASURE_SIZE * 3, height=MEASURE_SIZE * 3)
        writer = pymupdf.TextWriter(page.rect)
        writer.append((MEASURE_SIZE, MEASURE_SIZE * 2), char, font=font, fontsize=MEASURE_SIZE)
        writer.write_text(page)
        image = page.get_pixmap(dpi=RENDER_DPI, colorspace=pymupdf.csGRAY).pil_image()
    return ink_extent(image, MEASURE_SIZE * 2 * scale, MEASURE_SIZE * scale)


def _used_glyphs(document: pymupdf.Document, pages: Sequence[int], families: Iterable[str]) -> Counter[tuple[str, str]]:
    wanted = set(families)
    used: Counter[tuple[str, str]] = Counter()
    spans = (
        span for number in pages for block in document[number - 1].get_text("rawdict")["blocks"]
        for line in block.get("lines", []) for span in line["spans"]
    )
    for span in spans:
        family = font_family(span["font"])
        if family in wanted:
            used.update((family, char["c"]) for char in span["chars"])
    return used


def _used_extents(document: pymupdf.Document, pages: Sequence[int], fonts: dict[str, pymupdf.Font]) -> list[tuple[float, float]]:
    extents = []
    for (family, char), occurrences in _used_glyphs(document, pages, fonts).items():
        extent = glyph_extent(fonts[family], char)
        if extent is not None:
            extents.extend([extent] * occurrences)
    return extents


def probe_document(document: pymupdf.Document, sample_pages: Sequence[int]) -> ProbeResult:
    fonts = font_usage(document)
    families = candidate_families(usage.family for usage in fonts)
    _, xrefs = _family_xrefs(document)
    loaded = {family: font for family in families if (font := _load_font(document, xrefs[family])) is not None}
    extents = _used_extents(document, sample_pages, loaded)
    profile = FontProfile(
        families,
        ascent=round(percentile([top for top, _ in extents], PERCENTILE) + MARGIN, 2),
        descent=round(percentile([bottom for _, bottom in extents], PERCENTILE) + MARGIN, 2),
    )
    zero_width: Counter[str] = Counter(
        glyph.char for number in sample_pages for line in page_lines(document[number - 1], profile)
        for glyph in line if glyph.is_anu and glyph.width < ZERO_WIDTH
    )
    logger.info("probed", extra={"fonts": len(fonts), "candidates": sorted(families), "lines": len(extents),
                                 "ascent": profile.ascent, "descent": profile.descent, "zero_width_glyphs": len(zero_width)})
    return ProbeResult(fonts, profile, zero_width)
