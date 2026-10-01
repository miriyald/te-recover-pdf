import pymupdf
from PIL import Image, ImageDraw

from anu_unicode.probe import candidate_families, glyph_extent, ink_extent, percentile


def test_candidate_families_drop_latin_and_symbol_fonts() -> None:
    families = ["Priyaanka", "TimesNewRomanPS-BoldMT", "ZapfDingbats", "PallaviBold", "FuturaLtBT,Italic", "DingbitsOne"]

    assert candidate_families(families) == {"Priyaanka", "PallaviBold", "DingbitsOne"}


def test_ink_extent_is_measured_relative_to_baseline_and_size() -> None:
    image = Image.new("L", (100, 100), 255)
    ImageDraw.Draw(image).rectangle((10, 30, 40, 79), fill=0)

    top, bottom = ink_extent(image, baseline_px=70, size_px=40) or (0, 0)

    assert (top, bottom) == (1.0, 0.25)


def test_blank_clip_has_no_extent() -> None:
    assert ink_extent(Image.new("L", (50, 50), 255), baseline_px=25, size_px=10) is None


def test_glyph_extent_reads_ink_straight_from_the_font() -> None:
    font = pymupdf.Font("helv")

    capital = glyph_extent(font, "H")
    descender = glyph_extent(font, "g")

    assert capital is not None and descender is not None
    assert 0.6 < capital[0] < 0.85 and capital[1] < 0.05
    assert descender[1] > 0.1


def test_percentile_picks_upper_tail_without_outlier_dominance() -> None:
    values = [0.5] * 18 + [0.6, 2.0]

    assert percentile(values, 0.9) == 0.6
