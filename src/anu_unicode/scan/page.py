from dataclasses import dataclass

import numpy as np
import pymupdf
from scipy import ndimage

from anu_unicode.scan.ink import Component, find_components, letter_height, median_height, render_ink
from anu_unicode.scan.words import ScanWord, page_words

MIN_AREA = 40
FURNITURE_WIDTH = 6.8
MARGIN_ZONE = 0.15
SPECK_SIZE = 0.25
WORD_GAP = 0.38
STACK_GAP = 0.25


@dataclass(frozen=True)
class ScanPage:
    number: int
    body_height: float
    letter_height: float
    lines: list[list[ScanWord]]


def _inside(inner: Component, outer: Component) -> bool:
    return inner is not outer and outer.bbox[0] <= inner.bbox[0] and outer.bbox[1] <= inner.bbox[1] \
        and inner.bbox[2] <= outer.bbox[2] and inner.bbox[3] <= outer.bbox[3]


def _text_area(rules: list[Component], page_height: int) -> tuple[int, int]:
    head = [rule.bbox[3] for rule in rules if rule.bbox[1] < MARGIN_ZONE * page_height]
    foot = [rule.bbox[1] for rule in rules if rule.bbox[3] > (1 - MARGIN_ZONE) * page_height]
    return max(head, default=0), min(foot, default=page_height)


def _in_hole(inner: Component, outer: Component) -> bool:
    background, _ = ndimage.label(np.pad(~outer.mask, 1, constant_values=True))
    row = (inner.bbox[1] + inner.bbox[3]) // 2 - outer.bbox[1] + 1
    column = (inner.bbox[0] + inner.bbox[2]) // 2 - outer.bbox[0] + 1
    return bool(background[row, column] > 1)


def _with_dot(outer: Component, dot: Component) -> Component:
    mask = outer.mask.copy()
    top, left = dot.bbox[1] - outer.bbox[1], dot.bbox[0] - outer.bbox[0]
    mask[top:top + dot.height, left:left + dot.width] |= dot.mask
    return Component(outer.bbox, mask)


def text_components(components: list[Component], letter: float, page_height: int) -> list[Component]:
    rules = [component for component in components if component.width > FURNITURE_WIDTH * letter]
    top, bottom = _text_area(rules, page_height)
    text = [component for component in components
            if component.width <= FURNITURE_WIDTH * letter and top <= (component.bbox[1] + component.bbox[3]) / 2 <= bottom]
    hosts: dict[int, Component] = {}
    dropped: set[int] = set()
    for speck in (component for component in text if max(component.width, component.height) < SPECK_SIZE * letter):
        outer = next((other for other in text if _inside(speck, other)), None)
        if outer is not None:
            dropped.add(id(speck))
            if _in_hole(speck, outer):
                hosts[id(outer)] = _with_dot(hosts.get(id(outer), outer), speck)
    return [hosts.get(id(component), component) for component in text if id(component) not in dropped]


def scan_page(page: pymupdf.Page, number: int) -> ScanPage:
    ink = render_ink(page)
    components = find_components(ink, MIN_AREA)
    if not components:
        return ScanPage(number, 0.0, 0.0, [])
    letter = letter_height(components)
    text = text_components(components, letter, ink.shape[0])
    return ScanPage(number, median_height(components), letter, page_words(text, letter, WORD_GAP, STACK_GAP))
