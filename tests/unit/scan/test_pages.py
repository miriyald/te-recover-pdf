import pytest

from anu_unicode.scan.index import Occurrence
from anu_unicode.scan.pages import PageYield, rank_pages
from anu_unicode.scan.words import Band


def _at(page: int, word: int, shape_id: int) -> Occurrence:
    return Occurrence(page, 1, word, 1, shape_id, Band.MAIN, (0, 0, 10, 10))


def test_pages_are_ranked_by_the_new_shapes_each_adds() -> None:
    occurrences = [_at(1, 1, 7), _at(2, 1, 7), _at(2, 2, 8), _at(2, 3, 9), _at(3, 1, 7), _at(3, 2, 10)]

    ranked = rank_pages(occurrences, frozenset())

    assert [(item.page, item.shapes, item.new_shapes) for item in ranked] == [(2, 3, 3), (3, 2, 1), (1, 1, 0)]
    assert ranked[0].words == 3
    assert ranked[-1].covered_after == pytest.approx(1.0)


def test_excluded_shapes_count_for_nothing() -> None:
    ranked = rank_pages([_at(1, 1, 7), _at(1, 2, 8), _at(2, 1, 9)], frozenset({7, 8}))

    assert ranked[0] == PageYield(2, 1, 1, 1, 1.0)
