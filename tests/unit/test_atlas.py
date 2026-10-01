import io
from pathlib import Path

import pymupdf
from PIL import Image

from anu_unicode.atlas import RENDER_DPI, GlyphStats, glyph_stats, render_png, write_atlas
from anu_unicode.glyphs import Glyph, Word
from anu_unicode.shapes import Shape


def _word(text: str, marks: str = "") -> Word:
    return Word(tuple(Glyph(char, (0, 0, 0 if char in marks else 5, 10), 0, is_anu=True) for char in text))


def test_unit_is_drawn_from_the_first_font_that_has_all_its_glyphs() -> None:
    data = render_png([pymupdf.Font("helv")], "Hi", 40)

    assert data is not None and data.startswith(b"\x89PNG")


def test_unit_missing_from_every_font_is_not_drawn() -> None:
    assert render_png([pymupdf.Font("helv")], "క", 40) is None


def test_drawing_is_trimmed_to_the_ink_horizontally_but_keeps_its_height() -> None:
    data = render_png([pymupdf.Font("helv")], ".", 40)

    assert data is not None
    width, height = Image.open(io.BytesIO(data)).size
    assert width < 40 * RENDER_DPI / 72
    assert height == round(80 * RENDER_DPI / 72)


def test_glyph_stats_count_glyphs_and_list_their_units_and_words() -> None:
    words = [_word("=ˆ#", marks="ˆ"), _word("=ˆ#", marks="ˆ"), _word("#ˆ", marks="ˆ")]

    stats = {item.glyph: item for item in glyph_stats(words)}

    assert stats["#"] == GlyphStats("#", 3, False, ("#ˆ",), ("=ˆ#", "#ˆ"))
    assert stats["ˆ"] == GlyphStats("ˆ", 3, True, ("=ˆ", "#ˆ"), ("=ˆ#", "#ˆ"))
    assert [item.count for item in glyph_stats(words)] == [3, 3, 2]


def test_atlas_prefills_names_and_exports_every_named_row(tmp_path: Path) -> None:
    path = tmp_path / "atlas.html"
    stats = [GlyphStats("H", 30, False, (), ("Hi",)), GlyphStats("o", 10, True, ("Ho",), ())]

    write_atlas(path, stats, {"H": Shape("H", "ka_base", "క")}, [pymupdf.Font("helv")])

    page = path.read_text(encoding="utf-8")
    assert '<tr data-glyph="H">' in page and '<tr data-glyph="o">' in page
    assert 'class=n value="ka_base"' in page and 'class=c value="క"' in page
    assert "2 glyph codes in 40 occurrences, 1 named" in page
    assert "U+0048" in page
    assert "glyph\\tname\\tunicode" in page
