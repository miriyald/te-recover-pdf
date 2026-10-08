from anu_unicode.scan.conversion import Choice, convert_scan_page, readable
from anu_unicode.scan.index import EQUALS, Occurrence
from anu_unicode.scan.inference import Label, Source
from anu_unicode.scan.names import Speller
from anu_unicode.scan.source import shape_char
from anu_unicode.scan.word_ocr import words_of
from anu_unicode.scan.words import Band

SPELLER = Speller([])
LABELS = {1: Label("క", Source.WORDS, 9, 1.0), 2: Label("ా", Source.WORDS, 9, 1.0), 3: Label("ము", Source.WORDS, 9, 1.0)}


def _at(line: int, word: int, position: int, shape_id: int) -> Occurrence:
    return Occurrence(4, line, word, position, shape_id, Band.MAIN, (position * 50, line * 100, position * 50 + 40, line * 100 + 50))


def test_each_word_takes_ours_when_it_agrees_equals_bars_become_equals_and_the_rest_take_word_ocr() -> None:
    occurrences = [_at(1, 1, 1, 1), _at(1, 1, 2, 2), _at(1, 2, 1, EQUALS), _at(1, 2, 2, EQUALS), _at(1, 3, 1, 3),
                   _at(2, 1, 1, 3), _at(2, 1, 2, 77)]
    texts = {(4, 1, 1): "కా", (4, 1, 3): "మ", (4, 2, 1): "'ముల"}

    page = convert_scan_page(words_of(occurrences), LABELS, texts, SPELLER)

    assert page.lines == ["కా = మ", "ముల"]
    assert page.choices == {Choice.AGREED: 1, Choice.EQUALS: 1, Choice.WORD_OCR: 2}
    assert page.disagreements == [((4, 1, 3), "ము", "మ")]


def test_a_word_with_a_reviewed_id_keeps_our_reading_over_word_ocr() -> None:
    labels = {**LABELS, 3: Label("ము", Source.REVIEW, 0, 0.0)}

    page = convert_scan_page(words_of([_at(1, 1, 1, 3)]), labels, {(4, 1, 1): "మ"}, SPELLER)

    assert page.lines == ["ము"]
    assert page.choices == {Choice.REVIEWED: 1}


def test_a_word_that_starts_with_a_dependent_sign_joins_the_word_before_it() -> None:
    labels = {**LABELS, 9: Label("ః", Source.REVIEW, 0, 0.0)}
    occurrences = [_at(1, 1, 1, 1), _at(1, 2, 1, 9), _at(1, 3, 1, 3)]

    page = convert_scan_page(words_of(occurrences), labels, {(4, 1, 1): "క", (4, 1, 2): "8", (4, 1, 3): "ము"}, SPELLER)

    assert page.lines == ["కః ము"]


def test_a_dependent_sign_never_joins_an_equals_sign() -> None:
    labels = {**LABELS, 9: Label("ః", Source.REVIEW, 0, 0.0)}
    occurrences = [_at(1, 1, 1, EQUALS), _at(1, 1, 2, EQUALS), _at(1, 2, 1, 9)]

    page = convert_scan_page(words_of(occurrences), labels, {(4, 1, 2): "8"}, SPELLER)

    assert page.lines == ["= ః"]


def test_a_period_before_a_joined_dependent_sign_is_dropped_as_invented() -> None:
    labels = {**LABELS, 9: Label("ః", Source.REVIEW, 0, 0.0)}
    occurrences = [_at(1, 1, 1, 1), _at(1, 1, 2, 77), _at(1, 2, 1, 9)]

    page = convert_scan_page(words_of(occurrences), labels, {(4, 1, 1): "కై.", (4, 1, 2): "8"}, SPELLER)

    assert page.lines == ["కైః"]


def test_a_reviewed_id_does_not_override_ocr_when_a_neighbour_is_weak() -> None:
    labels = {1: Label("క", Source.WORDS, 2, 0.5), 3: Label("ము", Source.REVIEW, 0, 0.0)}

    page = convert_scan_page(words_of([_at(1, 1, 1, 1), _at(1, 1, 2, 3)]), labels, {(4, 1, 1): "కమ"}, SPELLER)

    assert page.lines == ["కమ"]
    assert page.disagreements == [((4, 1, 1), "కము", "కమ")]


def test_a_word_tesseract_cannot_read_is_written_only_from_reviewed_ids() -> None:
    words = words_of([_at(1, 1, 1, 1), _at(1, 2, 1, 3), _at(1, 3, 1, 1)])
    labels = {**LABELS, 3: Label("ము", Source.REVIEW, 0, 0.0)}

    page = convert_scan_page(words, labels, {(4, 1, 3): "క"}, SPELLER)

    assert page.lines == ["ము క"]
    assert page.choices == {Choice.UNREAD: 1, Choice.REVIEWED: 1, Choice.AGREED: 1}


def test_a_reviewed_name_no_recipe_covers_falls_back_to_word_ocr() -> None:
    labels = {**LABELS, 4: Label("o_tick", Source.REVIEW, 0, 0.0)}

    page = convert_scan_page(words_of([_at(1, 1, 1, 1), _at(1, 1, 2, 4)]), labels, {(4, 1, 1): "కో"}, SPELLER)

    assert page.lines == ["కో"]
    assert page.choices == {Choice.WORD_OCR: 1}


def test_a_word_with_no_ocr_and_an_unlabelled_id_shows_the_numbered_gap() -> None:
    page = convert_scan_page(words_of([_at(1, 1, 1, 1), _at(1, 1, 2, 77)]), LABELS, {}, SPELLER)

    assert page.lines == ["క⟦#77⟧"]
    assert page.choices == {Choice.GAP: 1}


def test_readable_replaces_only_shape_characters() -> None:
    assert readable("ము" + shape_char(12)) == "ము#12"
