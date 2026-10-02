from dataclasses import dataclass
from enum import StrEnum

import numpy as np

from anu_unicode.scan.ink import Box, Component

MIN_OVERLAP = 0.3
MAIN_OVERLAP = 0.5
BODY_HEIGHT_RANGE = (0.7, 1.3)


class Band(StrEnum):
    MAIN = "main"
    ABOVE = "above"
    BELOW = "below"


@dataclass(frozen=True)
class Placed:
    component: Component
    band: Band


@dataclass(frozen=True)
class ScanWord:
    glyphs: tuple[Placed, ...]
    band: tuple[int, int]

    @property
    def bbox(self) -> Box:
        boxes = [placed.component.bbox for placed in self.glyphs]
        return min(box[0] for box in boxes), min(box[1] for box in boxes), max(box[2] for box in boxes), max(box[3] for box in boxes)


def _overlap(first: tuple[int, int], second: tuple[int, int]) -> int:
    return min(first[1], second[1]) - max(first[0], second[0])


def _joined(first: Component, second: Component, word_gap: float, stack_gap: float) -> bool:
    horizontal = (first.bbox[0], first.bbox[2]), (second.bbox[0], second.bbox[2])
    vertical = (first.bbox[1], first.bbox[3]), (second.bbox[1], second.bbox[3])
    side_by_side = _overlap(*vertical) >= MIN_OVERLAP * min(first.height, second.height) and -_overlap(*horizontal) <= word_gap
    stacked = _overlap(*horizontal) >= MIN_OVERLAP * min(first.width, second.width) and -_overlap(*vertical) <= stack_gap
    return side_by_side or stacked


def _groups(components: list[Component], word_gap: float, stack_gap: float) -> list[list[Component]]:
    parent = list(range(len(components)))

    def root(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    by_left = sorted(range(len(components)), key=lambda index: components[index].bbox[0])
    for position, first in enumerate(by_left):
        reach = components[first].bbox[2] + word_gap
        for second in by_left[position + 1:]:
            if components[second].bbox[0] > reach:
                break
            if _joined(components[first], components[second], word_gap, stack_gap):
                parent[root(second)] = root(first)
    groups: dict[int, list[Component]] = {}
    for index, component in enumerate(components):
        groups.setdefault(root(index), []).append(component)
    return list(groups.values())


def _band(components: list[Component], body_height: float) -> tuple[int, int]:
    low, high = BODY_HEIGHT_RANGE
    body = [component for component in components if low * body_height <= component.height <= high * body_height] or components
    return int(np.median([component.bbox[1] for component in body])), int(np.median([component.bbox[3] for component in body]))


def classify(component: Component, band: tuple[int, int]) -> Band:
    if _overlap((component.bbox[1], component.bbox[3]), band) >= MAIN_OVERLAP * component.height:
        return Band.MAIN
    return Band.ABOVE if component.bbox[3] <= (band[0] + band[1]) / 2 else Band.BELOW


def _host(mark: Component, hosts: list[Placed]) -> int:
    span = (mark.bbox[0], mark.bbox[2])
    centre = (mark.bbox[0] + mark.bbox[2]) / 2
    return max(range(len(hosts)), key=lambda index: (
        _overlap(span, (hosts[index].component.bbox[0], hosts[index].component.bbox[2])),
        -abs(centre - (hosts[index].component.bbox[0] + hosts[index].component.bbox[2]) / 2),
    ))


def _drawing_order(placed: list[Placed]) -> tuple[Placed, ...]:
    hosts = sorted((item for item in placed if item.band is Band.MAIN), key=lambda item: item.component.bbox[0])
    marks = sorted((item for item in placed if item.band is not Band.MAIN),
                   key=lambda item: (item.band is Band.BELOW, item.component.bbox[0]))
    if not hosts:
        return tuple(sorted(marks, key=lambda item: item.component.bbox[0]))
    attached: list[list[Placed]] = [[] for _ in hosts]
    for mark in marks:
        attached[_host(mark.component, hosts)].append(mark)
    return tuple(item for host, own in zip(hosts, attached) for item in (host, *own))


def page_words(components: list[Component], body_height: float, word_gap: float, stack_gap: float) -> list[list[ScanWord]]:
    words = []
    for group in _groups(components, word_gap * body_height, stack_gap * body_height):
        band = _band(group, body_height)
        words.append(ScanWord(_drawing_order([Placed(component, classify(component, band)) for component in group]), band))
    return _lines(words)


def _lines(words: list[ScanWord]) -> list[list[ScanWord]]:
    lines: list[list[ScanWord]] = []
    for word in sorted(words, key=lambda item: item.band[0]):
        height = word.band[1] - word.band[0]
        line = next((line for line in lines if _overlap(line[-1].band, word.band) >= MAIN_OVERLAP * height), None)
        if line is None:
            lines.append([word])
        else:
            line.append(word)
    return [sorted(line, key=lambda item: item.bbox[0]) for line in lines]
