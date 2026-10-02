from pathlib import Path

import numpy as np

from anu_unicode.scan.atlas import (  # pylint: disable=protected-access
    AtlasInput,
    AtlasRow,
    Crop,
    Ocr,
    _ranked_for,
    largest_component,
    majority,
    propose_all,
    ranked_ids,
    same_shape_ids,
    spread,
    write_scan_atlas,
)
from anu_unicode.scan.catalog import ShapeCatalog, Thresholds, shape_of
from anu_unicode.scan.index import Occurrence
from anu_unicode.scan.ink import Component
from anu_unicode.scan.source import shape_char
from anu_unicode.scan.words import Band
from anu_unicode.shape_naming.shapes import Shape

BODY = 50.0


def _occurrence(shape_id: int, page: int = 4) -> Occurrence:
    return Occurrence(page, 1, 1, 1, shape_id, Band.MAIN, (0, 0, 10, 10))


def _ring() -> np.ndarray:
    mask = np.ones((50, 50), dtype=bool)
    mask[8:-8, 8:-8] = False
    return mask


def test_ids_are_ranked_by_count_and_rare_ones_left_out() -> None:
    occurrences = [_occurrence(2), _occurrence(5), _occurrence(5), _occurrence(5), _occurrence(2), _occurrence(9)]

    assert ranked_ids(occurrences, min_count=2, excluded=frozenset()) == [(5, 3, "main"), (2, 2, "main")]


def test_excluded_ids_are_left_out_of_the_atlas() -> None:
    occurrences = [_occurrence(2), _occurrence(5), _occurrence(5), _occurrence(2)]

    assert ranked_ids(occurrences, min_count=1, excluded=frozenset({5})) == [(2, 2, "main")]


def test_samples_are_spread_over_all_occurrences() -> None:
    items = [_occurrence(1, page) for page in range(10)]

    assert [item.page for item in spread(items, 3)] == [0, 4, 9]


def test_the_crop_keeps_only_the_largest_component_in_the_box() -> None:
    ink = np.zeros((20, 20), dtype=bool)
    ink[2:12, 2:12] = True
    ink[15:17, 15:17] = True

    assert largest_component(ink, (0, 0, 20, 20)).sum() == 100


def test_the_proposal_is_the_majority_reading_ignoring_blanks() -> None:
    assert majority(["క", "", "క", "ఉ"]) == ("క", 2)
    assert majority(["", ""]) == ("", 0)


def test_proposals_are_cached_and_not_read_again(tmp_path: Path) -> None:
    cache = tmp_path / "scan-ocr.tsv"
    crops = {3: [Crop(_ring(), BODY)] * 2}
    calls: list[int] = []

    def reader(mask: np.ndarray) -> str:
        calls.append(int(mask.sum()))
        return "ం"

    first = propose_all(crops, Ocr(reader, cache))
    second = propose_all(crops, Ocr(reader, cache))

    assert first == second == {3: ("ం", 2)}
    assert len(calls) == 2


def test_an_id_whose_members_pass_another_prototype_is_suggested_as_the_same() -> None:
    catalog = ShapeCatalog(Thresholds(0.2, 0.2, 0.25))
    for mask in (_ring(), np.roll(_ring(), 1, axis=1)):
        catalog._add(shape_of(Component((0, 0, 50, 50), mask), Band.MAIN, BODY))  # pylint: disable=protected-access
        catalog.counts[-1] = 1

    assert same_shape_ids(catalog, 1, [Crop(_ring(), BODY)], frozenset()) == (0,)
    assert not same_shape_ids(catalog, 1, [Crop(_ring(), BODY)], frozenset({0}))


def test_atlas_rows_carry_the_private_use_glyph_and_prefilled_names(tmp_path: Path) -> None:
    rows = [AtlasRow(7, 40, "main", "ము", 4, (12,), ("words/7-0.png",))]
    shapes = {shape_char(7): Shape(shape_char(7), "ము", "ము")}

    write_scan_atlas(tmp_path / "atlas.html", rows, shapes, "../scan-index/shapes")

    page = (tmp_path / "atlas.html").read_text(encoding="utf-8")
    assert f'data-glyph="{shape_char(7)}"' in page
    assert 'data-same="12"' in page
    assert 'value="ము"' in page
    assert "../scan-index/shapes/7.png" in page


def test_a_page_scoped_atlas_lists_every_id_on_the_page_with_book_counts() -> None:
    occurrences = [_occurrence(2, page=51), _occurrence(2, page=60), _occurrence(5, page=51), _occurrence(9, page=60)]
    catalog = ShapeCatalog(Thresholds(0.2, 0.2, 0.25))
    source = AtlasInput(None, occurrences, catalog, frozenset({5}), frozenset({51}))  # type: ignore[arg-type]

    assert _ranked_for(source, min_count=3) == [(2, 2, "main")]
