import pytest

from anu_unicode.convert import Coverage, convert_anu, convert_line, convert_segments
from anu_unicode.glyphs import Glyph

MAPPING = {"=": "వ", "=∞": "మ", "=Ú": "ము", "#": "న"}


def test_longest_sequence_wins() -> None:
    coverage = Coverage()

    text = convert_anu("=∞#=Ú=", MAPPING, coverage)

    assert text == "మనమువ"
    assert coverage.ratio == 1.0


def test_word_final_virama_gets_zwnj_from_any_mapping() -> None:
    assert convert_anu("=∞#±", {**MAPPING, "±": "్"}, Coverage()) == "మన్‌"


def test_segments_merge_adjacent_unmapped_glyphs_into_one_gap() -> None:
    segments = convert_segments("#º¯=∞", MAPPING)

    assert segments == [("#", "న"), ("º¯", None), ("=∞", "మ")]


@pytest.mark.parametrize(
    ("anu", "expected"),
    [("[~°`å¯~°∞x", "జరత్కారుని"), ("HõKÕÛù^Œ=Ú", "కచ్ఛేదము"), ("Hõ}ﬁ", "కణ్వ")],
)
def test_subscript_after_vowel_sign_is_reordered(anu: str, expected: str) -> None:
    mapping = {"[": "జ", "~°": "ర", "`å": "తా", "¯": "్క", "~°∞": "రు", "x": "ని", "Hõ": "క",
               "KÕ": "చే", "Ûù": "్ఛ", "^Œ": "ద", "=Ú": "ము", "}": "ణ", "ﬁ": "్వ"}

    text = convert_anu(anu, mapping, Coverage())

    assert text == expected


def test_unmapped_glyphs_are_wrapped_and_counted() -> None:
    coverage = Coverage()

    text = convert_anu("#º¯ =∞", MAPPING, coverage)

    assert text == "న⟦º¯⟧ మ"
    assert coverage.unmapped == {"º¯": 1}
    assert coverage.glyphs == 5
    assert coverage.ratio == 3 / 5


def test_convert_line_passes_non_anu_glyphs_through() -> None:
    line = [Glyph("=", (0, 0, 1, 1), 0, True), Glyph("∞", (1, 0, 2, 1), 1, True), Glyph("2", (3, 0, 4, 1), 3, False)]

    text = convert_line(line, MAPPING, Coverage())

    assert text == "మ2"
