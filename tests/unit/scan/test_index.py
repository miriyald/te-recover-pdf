from pathlib import Path

import numpy as np

from anu_unicode.scan.catalog import ShapeCatalog, Thresholds, shape_of
from anu_unicode.scan.index import EQUALS, AlphabetStats, ShapeIndex, alphabet_stats, write_index
from anu_unicode.scan.ink import Component
from anu_unicode.scan.page import ScanPage
from anu_unicode.scan.words import Band, Placed, ScanWord


def _word(*masks: np.ndarray) -> ScanWord:
    placed = tuple(Placed(Component((index * 60, 0, index * 60 + mask.shape[1], mask.shape[0]), mask), Band.MAIN)
                   for index, mask in enumerate(masks))
    return ScanWord(placed, (0, 50))


def test_stats_count_singletons_and_shapes_needed_for_99_percent() -> None:
    assert alphabet_stats([98, 1, 1, 0]) == AlphabetStats(shapes=3, singletons=2, shapes_for_coverage=2, occurrences=100)


def test_index_records_each_glyph_and_new_shapes_per_page(tmp_path: Path) -> None:
    square = np.ones((50, 50), dtype=bool)
    index = ShapeIndex(ShapeCatalog(Thresholds(0.15, 0.2, 0.25)))

    index.add(ScanPage(4, 50.0, 50.0, [[_word(square, square)]]))
    index.add(ScanPage(5, 50.0, 50.0, [[_word(square)]]))
    stats = write_index(tmp_path, index)

    assert [(item.page, item.position, item.shape_id) for item in index.occurrences] == [(4, 1, 0), (4, 2, 0), (5, 1, 0)]
    assert index.new_per_page == {4: 1, 5: 0}
    assert stats.shapes == 1
    assert (tmp_path / "shapes" / "0.png").exists()
    assert (tmp_path / "occurrences.tsv").read_text(encoding="utf-8").splitlines()[1] == "4\t1\t1\t1\t0\tmain\t0\t0\t50\t50\t2500"


def test_strips_from_an_earlier_run_are_removed(tmp_path: Path) -> None:
    (tmp_path / "shapes").mkdir()
    (tmp_path / "shapes" / "999.png").write_bytes(b"stale")
    index = ShapeIndex(ShapeCatalog(Thresholds(0.15, 0.2, 0.25)))
    index.add(ScanPage(4, 50.0, 50.0, [[_word(np.ones((50, 50), dtype=bool))]]))

    write_index(tmp_path, index)

    assert sorted(path.name for path in (tmp_path / "shapes").iterdir()) == ["0.png"]


def test_equals_bars_get_no_catalog_id_and_stay_out_of_the_statistics(tmp_path: Path) -> None:
    index = ShapeIndex(ShapeCatalog(Thresholds(0.15, 0.2, 0.25)))
    stroke = np.ones((10, 60), dtype=bool)
    top, bottom = Placed(Component((0, 10, 60, 20), stroke), Band.MAIN), Placed(Component((0, 30, 60, 40), stroke), Band.MAIN)
    equals = ScanWord((top, bottom), (0, 50))

    index.add(ScanPage(4, 50.0, 50.0, [[equals, _word(np.ones((50, 50), dtype=bool))]]))
    stats = write_index(tmp_path, index)

    assert [item.shape_id for item in index.occurrences] == [EQUALS, EQUALS, 0]
    assert len(index.catalog) == 1
    assert stats.occurrences == 1


def test_an_unchanged_component_keeps_its_earlier_id_and_a_changed_one_is_matched_again() -> None:
    square = np.ones((50, 50), dtype=bool)
    catalog = ShapeCatalog(Thresholds(0.15, 0.2, 0.25))
    for _ in range(4):
        catalog._add(shape_of(Component((0, 0, 50, 50), square), Band.MAIN, 50.0))  # pylint: disable=protected-access
    previous = {(4, (0, 0, 50, 50)): (3, 2500), (4, (60, 0, 110, 50)): (3, 999)}
    index = ShapeIndex(catalog, previous)

    index.add(ScanPage(4, 50.0, 50.0, [[_word(square, square)]]))

    assert [item.shape_id for item in index.occurrences] == [3, 0]
    assert index.kept == 1
    assert [item.ink for item in index.occurrences] == [2500, 2500]


def test_an_earlier_id_from_another_band_is_not_kept() -> None:
    square = np.ones((50, 50), dtype=bool)
    catalog = ShapeCatalog(Thresholds(0.15, 0.2, 0.25))
    catalog._add(shape_of(Component((0, 0, 50, 50), square), Band.ABOVE, 50.0))  # pylint: disable=protected-access
    index = ShapeIndex(catalog, {(4, (0, 0, 50, 50)): (0, 2500)})

    index.add(ScanPage(4, 50.0, 50.0, [[_word(square)]]))

    assert [item.shape_id for item in index.occurrences] == [1]
    assert index.kept == 0
