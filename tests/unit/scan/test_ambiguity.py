from pathlib import Path

import numpy as np

from anu_unicode.scan.ambiguity import Check, Verdict, check_index, matching_ids, write_ambiguity
from anu_unicode.scan.catalog import ShapeCatalog, Thresholds, shape_of
from anu_unicode.scan.index import Occurrence, ShapeIndex, write_index
from anu_unicode.scan.ink import Component
from anu_unicode.scan.page import ScanPage
from anu_unicode.scan.words import Band, Placed, ScanWord

BODY = 50.0


def _occurrence(shape_id: int) -> Occurrence:
    return Occurrence(4, 1, 1, 1, shape_id, Band.MAIN, (0, 0, 50, 50))


def _ring() -> np.ndarray:
    mask = np.ones((50, 50), dtype=bool)
    mask[8:-8, 8:-8] = False
    return mask


def _shape(mask: np.ndarray):
    return shape_of(Component((0, 0, mask.shape[1], mask.shape[0]), mask), Band.MAIN, BODY)


def test_verdict_is_clean_ambiguous_or_drifted() -> None:
    assert Check(_occurrence(3), ((3, 0),)).verdict is Verdict.CLEAN
    assert Check(_occurrence(3), ((3, 0), (7, 12))).verdict is Verdict.AMBIGUOUS
    assert Check(_occurrence(3), ((7, 12),)).verdict is Verdict.DRIFTED
    assert Check(_occurrence(3), ((3, 0), (7, 12))).rivals == [7]


def test_a_shape_matching_two_ids_lists_both_best_first() -> None:
    catalog = ShapeCatalog(Thresholds(0.2, 0.2, 0.25))
    catalog._add(_shape(_ring()))  # pylint: disable=protected-access
    catalog._add(_shape(np.roll(_ring(), 1, axis=1)))  # pylint: disable=protected-access

    matches = matching_ids(catalog, _shape(_ring()))

    assert [shape_id for shape_id, _ in matches] == [0, 1]


def test_report_flags_shared_occurrences_and_writes_its_own_folder(tmp_path: Path) -> None:
    catalog = ShapeCatalog(Thresholds(0.2, 0.2, 0.25))
    index = ShapeIndex(catalog)
    page = ScanPage(4, BODY, [[ScanWord((Placed(Component((0, 0, 50, 50), _ring()), Band.MAIN),), (0, 50))]])
    index.add(page)
    write_index(tmp_path / "scan-index", index)
    catalog._add(_shape(np.roll(_ring(), 1, axis=1)))  # pylint: disable=protected-access
    catalog.counts[1] = 1

    report = check_index(index, [page])
    write_ambiguity(tmp_path / "scan-ambiguity", report, catalog, "../scan-index/shapes")

    assert report.verdicts()[Verdict.AMBIGUOUS] == 1
    assert report.shared() == {(0, 1): 1}
    assert (0, 1) in report.prototype_pairs
    assert (tmp_path / "scan-ambiguity" / "pairs" / "0-1.png").exists()
    assert (tmp_path / "scan-ambiguity" / "confusable.tsv").read_text(encoding="utf-8").splitlines()[1] == "0\t1\t1\t1\t1\tTrue"
