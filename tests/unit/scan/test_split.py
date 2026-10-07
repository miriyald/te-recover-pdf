import numpy as np

from anu_unicode.scan.catalog import to_canvas
from anu_unicode.scan.index import Occurrence
from anu_unicode.scan.inference import Label, Source
from anu_unicode.scan.names import Speller
from anu_unicode.scan.split import Mixed, divide, find_mixed, readings
from anu_unicode.scan.word_ocr import words_of
from anu_unicode.scan.words import Band

BODY = 50.0


def _at(page: int, word: int, position: int, shape_id: int) -> Occurrence:
    return Occurrence(page, 1, word, position, shape_id, Band.MAIN, (position * 60, 0, position * 60 + 50, 50))


def _square() -> np.ndarray:
    return to_canvas(np.ones((50, 50), dtype=bool), BODY)


def _ring() -> np.ndarray:
    mask = np.ones((50, 50), dtype=bool)
    mask[8:-8, 8:-8] = False
    return to_canvas(mask, BODY)


def test_each_occurrence_is_read_from_its_own_word_when_its_id_agrees_poorly() -> None:
    occurrences = [_at(4, 1, 1, 1), _at(4, 1, 2, 2), _at(4, 2, 1, 1), _at(4, 2, 2, 2), _at(4, 3, 1, 3)]
    labels = {1: Label("డ", Source.WORDS, 1, 0.5), 2: Label("ము", Source.WORDS, 9, 1.0), 3: Label("క", Source.WORDS, 9, 1.0)}

    found = readings(words_of(occurrences), {(4, 1, 1): "డము", (4, 1, 2): "దము", (4, 1, 3): "క"}, labels, Speller([]), frozenset())

    assert found == {1: {occurrences[0]: "డ", occurrences[2]: "ద"}}


def test_two_stable_readings_make_an_id_mixed_and_its_decision_keeps_its_side() -> None:
    by_id = {1: {_at(4, word, 1, 1): "ద" if word <= 7 else "డ" for word in range(1, 13)}}
    labels = {1: Label("డ", Source.REVIEW, 0, 0.4)}

    assert find_mixed(by_id, labels) == [Mixed(1, keep="డ", other="ద", kept=5, other_count=7)]


def test_a_rare_second_reading_or_too_few_words_is_not_a_mix() -> None:
    rare = {1: {_at(4, word, 1, 1): "ద" if word == 1 else "డ" for word in range(1, 11)}}
    few = {1: {_at(4, word, 1, 1): "ద" if word <= 3 else "డ" for word in range(1, 7)}}
    labels = {1: Label("డ", Source.WORDS, 0, 0.4)}

    assert not find_mixed(rare, labels)
    assert not find_mixed(few, labels)


def test_a_mixed_id_is_divided_by_the_nearer_template_including_unread_occurrences() -> None:
    squares, rings = [_at(4, word, 1, 1) for word in range(1, 6)], [_at(5, word, 1, 1) for word in range(1, 6)]
    unread = _at(6, 1, 1, 1)
    canvases = {**{item: _square() for item in squares}, **{item: _ring() for item in rings}, unread: _ring()}
    read = {**{item: "డ" for item in squares}, **{item: "ద" for item in rings}}

    division = divide(Mixed(1, "డ", "ద", 5, 5), canvases, read)

    assert division is not None
    assert set(division.move) == {*rings, unread}


def test_readings_that_look_the_same_are_not_divided() -> None:
    items = [_at(4, word, 1, 1) for word in range(1, 11)]

    assert divide(Mixed(1, "డ", "ద", 5, 5), {item: _square() for item in items},
                  {item: "డ" if index < 5 else "ద" for index, item in enumerate(items)}) is None
