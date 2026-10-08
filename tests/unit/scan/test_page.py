import io

import numpy as np
import pymupdf
from PIL import Image

from anu_unicode.scan.ink import Component, letter_height, median_height
from anu_unicode.scan.page import scan_page, text_components
from anu_unicode.scan.profile import Grouping, ScanProfile

BODY = 50.0
PAGE_HEIGHT = 1000


def _block(left: int, top: int, width: int, height: int) -> Component:
    return Component((left, top, left + width, top + height), np.ones((height, width), dtype=bool))


def test_letter_height_follows_the_letters_not_the_many_small_marks() -> None:
    letters = [_block(index * 60, 0, 40, height) for index, height in enumerate((60, 62, 63, 64))]
    marks = [_block(index * 30, 100, 20, height) for index, height in enumerate((10, 12, 28, 30, 38, 40))]

    assert median_height([*letters, *marks]) == 39.0
    assert letter_height([*letters, *marks]) == 62.0


def test_a_blank_scanned_page_has_no_lines_and_no_heights() -> None:
    white = io.BytesIO()
    Image.new("L", (200, 300), 255).save(white, format="PNG")
    document = pymupdf.open()
    document.new_page(width=200, height=300).insert_image(pymupdf.Rect(0, 0, 200, 300), stream=white.getvalue())

    page = scan_page(document[0], 1, ScanProfile())

    assert (page.body_height, page.lines) == (0.0, [])


REPAIR = Grouping(repair_size=0.4, repair_gap=0.08)


def test_a_small_fragment_almost_touching_its_letter_is_joined_back_to_it() -> None:
    letter, fragment = _block(100, 100, 40, 50), _block(142, 95, 8, 8)

    kept = text_components([letter, fragment], BODY, PAGE_HEIGHT, REPAIR)

    assert [component.bbox for component in kept] == [(100, 95, 150, 150)]
    assert int(kept[0].mask.sum()) == 40 * 50 + 8 * 8


def test_a_small_mark_further_away_or_a_large_piece_close_by_stays_separate() -> None:
    letter, mark, subscript = _block(100, 100, 40, 50), _block(150, 95, 8, 8), _block(100, 152, 40, 30)

    kept = text_components([letter, mark, subscript], BODY, PAGE_HEIGHT, REPAIR)

    assert len(kept) == 3


def test_a_fragment_joins_the_nearer_of_two_letters() -> None:
    far, near, fragment = _block(100, 100, 40, 50), _block(155, 100, 40, 50), _block(143, 95, 10, 8)

    kept = text_components([far, near, fragment], BODY, PAGE_HEIGHT, REPAIR)

    assert sorted(component.bbox for component in kept) == [(100, 100, 140, 150), (143, 95, 195, 150)]


def test_a_fragment_close_only_to_another_fragment_is_not_chained_onto_the_letter() -> None:
    letter, first, second = _block(100, 100, 40, 50), _block(142, 95, 8, 8), _block(152, 95, 8, 8)

    kept = text_components([letter, first, second], BODY, PAGE_HEIGHT, REPAIR)

    assert sorted(component.bbox for component in kept) == [(100, 95, 150, 150), (152, 95, 160, 103)]


def test_fragments_stay_separate_when_the_profile_does_not_repair_strokes() -> None:
    kept = text_components([_block(100, 100, 40, 50), _block(142, 95, 8, 8)], BODY, PAGE_HEIGHT, Grouping())

    assert len(kept) == 2


def test_running_head_and_footer_between_the_ornament_rules_are_dropped() -> None:
    head_rule, head_text = _block(0, 60, 900, 10), _block(0, 10, 40, 40)
    foot_rule, page_number = _block(0, 930, 900, 10), _block(400, 945, 30, 40)
    body = _block(0, 400, 40, 50)

    kept = text_components([head_rule, head_text, body, foot_rule, page_number], BODY, PAGE_HEIGHT, Grouping())

    assert kept == [body]


def test_a_speck_enclosed_by_a_letter_is_noise_but_a_free_speck_is_kept() -> None:
    letter, enclosed, free = _block(100, 400, 40, 50), _block(110, 410, 5, 5), _block(300, 400, 5, 5)

    kept = text_components([letter, enclosed, free], BODY, PAGE_HEIGHT, Grouping())

    assert kept == [letter, free]


def test_a_dot_inside_a_letters_hole_becomes_part_of_the_letter() -> None:
    mask = np.ones((50, 40), dtype=bool)
    mask[8:-8, 8:-8] = False
    ring, dot = Component((100, 400, 140, 450), mask), _block(117, 422, 6, 6)

    kept = text_components([ring, dot], BODY, PAGE_HEIGHT, Grouping())

    assert len(kept) == 1
    assert kept[0].bbox == ring.bbox
    assert kept[0].mask[22:28, 17:23].all()


def test_a_glyph_whose_subscript_reaches_past_the_foot_rule_is_kept() -> None:
    foot_rule, page_number = _block(0, 930, 900, 10), _block(400, 945, 30, 40)
    last_line = _block(0, 890, 40, 60)

    kept = text_components([foot_rule, page_number, last_line], BODY, PAGE_HEIGHT, Grouping())

    assert kept == [last_line]
