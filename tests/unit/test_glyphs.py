from dataclasses import replace
from typing import Any
from unittest.mock import MagicMock

from anu_unicode.glyphs import Glyph, Word, font_family, page_lines, split_words, symbol_text, type3_families
from anu_unicode.profile import DEFAULT_PROFILE


def _glyph(char: str, x0: float, width: float, is_anu: bool = True) -> Glyph:
    return Glyph(char, (x0, 0.0, x0 + width, 10.0), x0, is_anu)


def _char(char: str, x0: float, width: float, baseline: float) -> dict[str, Any]:
    return {"c": char, "bbox": (x0, baseline - 15, x0 + width, baseline), "origin": (x0, baseline)}


def _line(font: str, chars: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "bbox": (chars[0]["bbox"][0], 0, chars[-1]["bbox"][2], 0),
        "spans": [{"font": font, "size": 15.0, "origin": chars[0]["origin"], "chars": chars}],
    }


def test_units_attach_zero_width_glyphs_to_preceding_glyph() -> None:
    word = Word((_glyph("=", 0, 6.8), _glyph("∞", 6.8, 3.1), _glyph("H", 9.9, 5.7), _glyph("õ", 15.6, 0.0)))

    units = word.units

    assert units == ["=", "∞", "Hõ"]


def test_split_words_breaks_on_space_and_non_anu_glyphs() -> None:
    line = [_glyph("=", 0, 6), _glyph("∞", 6, 3), _glyph(" ", 9, 4), _glyph("x", 13, 6), _glyph("2", 19, 5, is_anu=False)]

    words = split_words(line)

    assert [word.text for word in words] == ["=∞", "x"]


def test_page_lines_merges_pieces_on_same_baseline_in_x_order() -> None:
    page = MagicMock()
    page.get_text.return_value = {"blocks": [{"lines": [
        _line("ABCDEF+Priyaanka", [_char("2", 300, 5, 100.0), _char("9", 305, 5, 100.0)]),
        _line("ABCDEF+Priyaanka", [_char("=", 80, 6, 100.5), _char("∞", 86, 3, 100.5)]),
        _line("ABCDEF+TimesNewRomanPS-BoldMT", [_char("x", 80, 6, 120.0)]),
    ]}]}

    lines = page_lines(page)

    assert ["".join(glyph.char for glyph in line) for line in lines] == ["=∞ 29", "x"]
    assert lines[0][0].is_anu and not lines[1][0].is_anu


def test_symbol_font_codes_become_anu_chars_in_anu_fonts_and_plain_bytes_elsewhere() -> None:
    page = MagicMock()
    page.get_text.return_value = {"blocks": [{"lines": [
        _line("ABCDEF+GowthamiThin", [_char("\uf03d", 80, 6, 100.0), _char("\uf0b0", 86, 3, 100.0), _char("\uf0c6", 89, 0, 100.0)]),
        _line("ABCDEF+TeluguNumbersBold", [_char("\uf02d", 80, 6, 120.0)]),
    ]}]}

    lines = page_lines(page)

    assert ["".join(glyph.char for glyph in line) for line in lines] == ["=∞Δ", "-"]


def test_text_in_type3_fonts_is_skipped_because_its_codes_mean_nothing() -> None:
    page = MagicMock()
    page.get_fonts.return_value = [(7, "n/a", "Type3", "M", "M", "")]
    page.get_text.return_value = {"blocks": [{"lines": [
        _line("M", [_char("\x16", 80, 6, 100.0)]),
        _line("ABCDEF+Priyaanka", [_char("=", 80, 6, 120.0), _char("∞", 86, 3, 120.0)]),
    ]}]}

    lines = page_lines(page)

    assert ["".join(glyph.char for glyph in line) for line in lines] == ["=∞"]
    assert type3_families(page) == {"M"}


def test_type1_characters_are_translated_to_anu_characters_only_when_the_profile_has_a_layout() -> None:
    page = MagicMock()
    page.get_fonts.return_value = [(7, "cff", "Type1", "ABCDEF+PallaviBold", "F3", "")]
    page.get_text.return_value = {"blocks": [{"lines": [_line("PallaviBold", [_char("V", 80, 6, 100.0), _char("æ", 86, 3, 100.0)])]}]}
    profile = replace(DEFAULT_PROFILE, type1_codes={"V": 0x41, "æ": 0xAC})

    translated = ["".join(glyph.char for glyph in line) for line in page_lines(page, profile)]
    untouched = ["".join(glyph.char for glyph in line) for line in page_lines(page)]

    assert translated == [DEFAULT_PROFILE.byte_char(0x41) + DEFAULT_PROFILE.byte_char(0xAC)]
    assert untouched == ["Væ"]


def test_pages_listed_as_plain_keep_their_type1_characters() -> None:
    page = MagicMock()
    page.number = 424
    page.get_fonts.return_value = [(7, "cff", "Type1", "ABCDEF+PallaviBold", "F3", "")]
    page.get_text.return_value = {"blocks": [{"lines": [_line("PallaviBold", [_char("V", 80, 6, 100.0)])]}]}
    profile = replace(DEFAULT_PROFILE, type1_codes={"V": 0x41}, type1_plain_pages=frozenset({425}))

    assert ["".join(glyph.char for glyph in line) for line in page_lines(page, profile)] == ["V"]


def test_style_suffix_does_not_hide_an_anu_family() -> None:
    assert font_family("ABCDEF+Priyaanka,Italic") == "Priyaanka"


def test_symbol_text_gives_the_codes_a_symbol_font_draws() -> None:
    assert symbol_text("=∞Δ", DEFAULT_PROFILE) == "\uf03d\uf0b0\uf0c6"
    assert symbol_text("=క", DEFAULT_PROFILE) is None


def test_page_lines_corrects_anu_vertical_extent_around_baseline() -> None:
    page = MagicMock()
    page.get_text.return_value = {"blocks": [{"lines": [_line("ABCDEF+Priyaanka", [_char("=", 80, 6, 100.0)])]}]}

    glyph = page_lines(page)[0][0]

    assert glyph.bbox[1] < 100.0 < glyph.bbox[3]
