from pathlib import Path

import pymupdf

from anu_unicode.shape_naming.atlas import GlyphStats
from anu_unicode.shape_naming.sheets import render_highlighted, write_sheets

FONTS = [pymupdf.Font("helv")]


def _has_red(image_bytes: Path) -> bool:
    with pymupdf.open(image_bytes) as document:
        pixmap = document[0].get_pixmap()
    return any(pixmap.pixel(x, y)[0] > 200 > pixmap.pixel(x, y)[1] for x in range(pixmap.width) for y in range(pixmap.height))


def test_target_glyph_is_drawn_red_inside_the_word(tmp_path: Path) -> None:
    image = render_highlighted(FONTS, "Hi", "i")
    assert image is not None
    path = tmp_path / "word.png"
    image.save(path)

    assert _has_red(path)


def test_text_missing_from_every_font_is_not_drawn() -> None:
    assert render_highlighted(FONTS, "క", "క") is None


def test_sheets_hold_a_fixed_number_of_glyph_rows(tmp_path: Path) -> None:
    stats = [GlyphStats(char, 10 - index, index == 0, (), (f"{char}x",)) for index, char in enumerate("abcde")]

    paths = write_sheets(tmp_path, stats, FONTS, per_sheet=2)

    assert [path.name for path in paths] == ["sheet-01.png", "sheet-02.png", "sheet-03.png"]
    assert all(path.exists() for path in paths)
