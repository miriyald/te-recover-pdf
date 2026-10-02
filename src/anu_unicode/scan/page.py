from dataclasses import dataclass

import pymupdf

from anu_unicode.scan.ink import Component, find_components, median_height, render_ink
from anu_unicode.scan.words import ScanWord, page_words

MIN_AREA = 40
FURNITURE_WIDTH = 8.0
MARGIN_ZONE = 0.15
SPECK_SIZE = 0.3
WORD_GAP = 0.45
STACK_GAP = 0.3


@dataclass(frozen=True)
class ScanPage:
    number: int
    body_height: float
    lines: list[list[ScanWord]]


def _inside(inner: Component, outer: Component) -> bool:
    return inner is not outer and outer.bbox[0] <= inner.bbox[0] and outer.bbox[1] <= inner.bbox[1] \
        and inner.bbox[2] <= outer.bbox[2] and inner.bbox[3] <= outer.bbox[3]


def _text_area(rules: list[Component], page_height: int) -> tuple[int, int]:
    head = [rule.bbox[3] for rule in rules if rule.bbox[1] < MARGIN_ZONE * page_height]
    foot = [rule.bbox[1] for rule in rules if rule.bbox[3] > (1 - MARGIN_ZONE) * page_height]
    return max(head, default=0), min(foot, default=page_height)


def text_components(components: list[Component], body_height: float, page_height: int) -> list[Component]:
    rules = [component for component in components if component.width > FURNITURE_WIDTH * body_height]
    top, bottom = _text_area(rules, page_height)
    text = [component for component in components
            if component.width <= FURNITURE_WIDTH * body_height and top <= component.bbox[1] and component.bbox[3] <= bottom]
    specks = [component for component in text if max(component.width, component.height) < SPECK_SIZE * body_height]
    enclosed = {id(speck) for speck in specks if any(_inside(speck, other) for other in text)}
    return [component for component in text if id(component) not in enclosed]


def scan_page(page: pymupdf.Page, number: int) -> ScanPage:
    ink = render_ink(page)
    components = find_components(ink, MIN_AREA)
    body_height = median_height(components)
    text = text_components(components, body_height, ink.shape[0])
    return ScanPage(number, body_height, page_words(text, body_height, WORD_GAP, STACK_GAP))
