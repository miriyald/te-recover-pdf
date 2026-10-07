from pathlib import Path

import numpy as np

from anu_unicode.scan.glyph_ocr import GlyphOcr, largest_component, majority, propose, spread
from anu_unicode.scan.index import Occurrence
from anu_unicode.scan.ink import Bitmap
from anu_unicode.scan.words import Band


def _occurrence(shape_id: int, page: int = 4) -> Occurrence:
    return Occurrence(page, 1, 1, 1, shape_id, Band.MAIN, (0, 0, 10, 10))


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


def test_a_reading_over_several_lines_is_cached_on_one_row(tmp_path: Path) -> None:
    ocr = GlyphOcr(lambda _mask: "క\nా", tmp_path / "glyph-ocr.tsv")
    ink = np.ones((20, 20), dtype=bool)

    propose([_occurrence(3)], lambda _page: ink, ocr)

    assert propose([_occurrence(3)], lambda _page: ink, ocr) == {3: ("క ా", 1)}


def test_proposals_are_read_from_sampled_crops_once_and_then_cached(tmp_path: Path) -> None:
    calls: list[int] = []

    def render(_page: int) -> Bitmap:
        ink = np.zeros((20, 20), dtype=bool)
        ink[2:8, 2:8] = True
        return ink

    def reader(mask: Bitmap) -> str:
        calls.append(int(mask.sum()))
        return "ం"

    occurrences = [_occurrence(3), _occurrence(3, page=5)]
    ocr = GlyphOcr(reader, tmp_path / "glyph-ocr.tsv")

    first = propose(occurrences, render, ocr)
    second = propose(occurrences, render, ocr)

    assert first == second == {3: ("ం", 2)}
    assert calls == [36, 36]
