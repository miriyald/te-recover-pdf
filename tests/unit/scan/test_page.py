import numpy as np

from anu_unicode.scan.ink import Component
from anu_unicode.scan.page import text_components

BODY = 50.0
PAGE_HEIGHT = 1000


def _block(left: int, top: int, width: int, height: int) -> Component:
    return Component((left, top, left + width, top + height), np.ones((height, width), dtype=bool))


def test_running_head_and_footer_between_the_ornament_rules_are_dropped() -> None:
    head_rule, head_text = _block(0, 60, 900, 10), _block(0, 10, 40, 40)
    foot_rule, page_number = _block(0, 930, 900, 10), _block(400, 945, 30, 40)
    body = _block(0, 400, 40, 50)

    kept = text_components([head_rule, head_text, body, foot_rule, page_number], BODY, PAGE_HEIGHT)

    assert kept == [body]


def test_a_speck_enclosed_by_a_letter_is_noise_but_a_free_speck_is_kept() -> None:
    letter, enclosed, free = _block(100, 400, 40, 50), _block(110, 410, 5, 5), _block(300, 400, 5, 5)

    kept = text_components([letter, enclosed, free], BODY, PAGE_HEIGHT)

    assert kept == [letter, free]
