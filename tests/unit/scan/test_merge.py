import numpy as np

from anu_unicode.scan.catalog import ShapeCatalog, Thresholds, shape_of
from anu_unicode.scan.index import Member, Occurrence, ShapeIndex
from anu_unicode.scan.ink import Component
from anu_unicode.scan.merge import duplicate_targets, merge_duplicates
from anu_unicode.scan.words import Band

BODY = 50.0


def _ring() -> np.ndarray:
    mask = np.ones((50, 50), dtype=bool)
    mask[8:-8, 8:-8] = False
    return mask


def _cup() -> np.ndarray:
    mask = _ring()
    mask[:8, 8:-8] = False
    return mask


def _index_with(*groups: tuple[np.ndarray, int]) -> ShapeIndex:
    index = ShapeIndex(ShapeCatalog(Thresholds(0.2, 0.2, 0.25)))
    for shape_id, (mask, count) in enumerate(groups):
        index.catalog._add(shape_of(Component((0, 0, 50, 50), mask), Band.MAIN, BODY))  # pylint: disable=protected-access
        for _ in range(count):
            index.catalog._count(shape_id, shape_of(Component((0, 0, 50, 50), mask), Band.MAIN, BODY))  # pylint: disable=protected-access
            index.occurrences.append(Occurrence(4, 1, 1, 1, shape_id, Band.MAIN, (0, 0, 50, 50)))
        index.members[shape_id] = [Member(mask, BODY)] * min(count, 4)
        index.pages[shape_id] = {4}
    return index


def test_a_smaller_duplicate_merges_into_the_larger_id() -> None:
    index = _index_with((_ring(), 5), (np.roll(_ring(), 1, axis=1), 2))

    assert duplicate_targets(index) == {1: 0}


def test_merging_relabels_occurrences_and_retires_the_source() -> None:
    index = _index_with((_ring(), 5), (np.roll(_ring(), 1, axis=1), 2))

    rounds = merge_duplicates(index)

    assert rounds == [1]
    assert {item.shape_id for item in index.occurrences} == {0}
    assert (index.catalog.counts[0], index.catalog.counts[1]) == (7.0, 0.0)
    assert 1 not in index.members


def test_a_different_shape_is_never_merged() -> None:
    index = _index_with((_ring(), 5), (_cup(), 2))

    assert not duplicate_targets(index)
