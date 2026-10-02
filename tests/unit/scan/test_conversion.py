from anu_unicode.convert import Coverage
from anu_unicode.scan.conversion import convert_scan_page, readable, unmapped_ids
from anu_unicode.scan.index import Occurrence
from anu_unicode.scan.source import shape_char
from anu_unicode.scan.words import Band

MAPPING = {shape_char(1): "క", shape_char(2): "ా", shape_char(3): "ము"}


def _at(line: int, word: int, position: int, shape_id: int) -> Occurrence:
    return Occurrence(4, line, word, position, shape_id, Band.MAIN, (position * 50, line * 100, position * 50 + 40, line * 100 + 50))


def test_lines_and_words_convert_in_order() -> None:
    occurrences = [_at(2, 1, 1, 3), _at(1, 2, 1, 3), _at(1, 1, 2, 2), _at(1, 1, 1, 1)]

    page = convert_scan_page(occurrences, frozenset(), MAPPING, 1.0, Coverage())

    assert page.lines == ["కా ము", "ము"]
    assert [text for _, text in page.words] == ["కా", "ము", "ము"]


def test_excluded_ids_contribute_nothing() -> None:
    occurrences = [_at(1, 1, 1, 1), _at(1, 1, 2, 9), _at(1, 1, 3, 2)]

    page = convert_scan_page(occurrences, frozenset({9}), MAPPING, 1.0, Coverage())

    assert page.lines == ["కా"]


def test_unnamed_ids_show_as_numbered_gaps_and_are_counted() -> None:
    coverage = Coverage()

    page = convert_scan_page([_at(1, 1, 1, 1), _at(1, 1, 2, 77), _at(1, 2, 1, 77)], frozenset(), MAPPING, 1.0, coverage)

    assert page.lines == ["క⟦#77⟧ ⟦#77⟧"]
    assert unmapped_ids(coverage) == {77: 2}


def test_readable_replaces_only_shape_characters() -> None:
    assert readable("ము" + shape_char(12)) == "ము#12"
