import numpy as np

from anu_unicode.scan.catalog import ShapeCatalog, Thresholds, shape_of
from anu_unicode.scan.ink import Component
from anu_unicode.scan.page import ScanPage
from anu_unicode.scan.split import frequent_alphabet, neck_columns, split_fused, split_page
from anu_unicode.scan.words import Band, Placed, ScanWord

BODY = 50.0
BAND = (0, 50)


def _ring(width: int = 40) -> np.ndarray:
    mask = np.ones((50, width), dtype=bool)
    mask[6:-6, 6:-6] = False
    return mask


def _sign() -> np.ndarray:
    mask = np.zeros((30, 24), dtype=bool)
    mask[:6, :] = True
    mask[:, -8:] = True
    return mask


def _fused() -> np.ndarray:
    return np.hstack([_ring(), np.vstack([_sign(), np.zeros((20, 24), dtype=bool)])])


def _catalog(*masks: np.ndarray) -> ShapeCatalog:
    catalog = ShapeCatalog(Thresholds(0.15, 0.2, 0.25))
    for mask in masks:
        catalog.assign(shape_of(Component((0, 0, mask.shape[1], mask.shape[0]), mask), Band.MAIN, BODY))
    return catalog


def test_a_neck_is_one_thin_run_of_ink_between_thicker_parts() -> None:
    assert 40 in neck_columns(_fused(), BODY)


def test_a_ring_and_a_solid_bar_have_no_neck() -> None:
    assert neck_columns(_ring(width=60), BODY) == []
    assert neck_columns(np.ones((10, 200), dtype=bool), BODY) == []


def test_a_base_touching_a_sign_is_cut_at_the_neck() -> None:
    alphabet = frequent_alphabet(_catalog(_ring(), _sign()), np.array([50.0, 50.0]), min_count=20)
    placed = Placed(Component((100, 0, 164, 50), _fused()), Band.MAIN)

    parts = split_fused(placed, BAND, BODY, alphabet, explained=False)

    assert [part.component.bbox for part in parts or ()] == [(100, 0, 140, 50), (140, 0, 164, 30)]


def test_an_explained_glyph_is_cut_only_when_both_parts_are_frequent() -> None:
    alphabet = frequent_alphabet(_catalog(_ring(), _sign()), np.array([3.0, 50.0]), min_count=20)
    placed = Placed(Component((0, 0, 64, 50), _fused()), Band.MAIN)

    assert split_fused(placed, BAND, BODY, alphabet, explained=True) is None


def test_one_frequent_part_is_enough_to_cut() -> None:
    alphabet = frequent_alphabet(_catalog(_ring(), _sign()), np.array([3.0, 50.0]), min_count=20)
    placed = Placed(Component((0, 0, 64, 50), _fused()), Band.MAIN)

    assert split_fused(placed, BAND, BODY, alphabet, explained=False) is not None


def test_nothing_is_cut_when_no_part_is_frequent() -> None:
    alphabet = frequent_alphabet(_catalog(_ring(), _sign()), np.array([3.0, 3.0]), min_count=20)
    placed = Placed(Component((0, 0, 64, 50), _fused()), Band.MAIN)

    assert split_fused(placed, BAND, BODY, alphabet, explained=False) is None


def test_split_page_replaces_a_fused_glyph_by_its_parts_in_drawing_order() -> None:
    alphabet = frequent_alphabet(_catalog(_ring(), _sign()), np.array([50.0, 50.0]), min_count=20)
    known = Placed(Component((200, 0, 240, 50), _ring()), Band.MAIN)
    fused = Placed(Component((0, 0, 64, 50), _fused()), Band.MAIN)

    page = split_page(ScanPage(7, BODY, [[ScanWord((fused, known), BAND)]]), alphabet)

    assert [placed.component.bbox[0] for placed in page.lines[0][0].glyphs] == [0, 40, 200]
