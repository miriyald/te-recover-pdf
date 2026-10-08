from dataclasses import dataclass
from enum import StrEnum

import numpy as np

from anu_unicode.scan.ink import Box, Component

MIN_OVERLAP = 0.3
MAIN_OVERLAP = 0.5
RESTING_OVERLAP = 0.5
RESTING_DEPTH = 0.25
BAR_HEIGHT = 0.35
BAR_ASPECT = 2.5
EQUALS_ALIGNMENT = 0.8
MAJORITY_DEPTH = 3


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


def _is_bar(component: Component, body_height: float) -> bool:
    return component.height < BAR_HEIGHT * body_height and component.width > BAR_ASPECT * component.height


def is_equals(word: ScanWord, body_height: float) -> bool:
    return len(word.glyphs) >= 2 and all(_is_bar(placed.component, body_height) for placed in word.glyphs)


def _overlap(first: tuple[int, int], second: tuple[int, int]) -> int:
    return min(first[1], second[1]) - max(first[0], second[0])


def _stacked(first: Component, second: Component, stack_gap: float) -> bool:
    horizontal = (first.bbox[0], first.bbox[2]), (second.bbox[0], second.bbox[2])
    vertical = (first.bbox[1], first.bbox[3]), (second.bbox[1], second.bbox[3])
    return _overlap(*horizontal) >= MIN_OVERLAP * min(first.width, second.width) and -_overlap(*vertical) <= stack_gap


def _joined(first: Component, second: Component, word_gap: float, stack_gap: float) -> bool:
    horizontal = (first.bbox[0], first.bbox[2]), (second.bbox[0], second.bbox[2])
    vertical = (first.bbox[1], first.bbox[3]), (second.bbox[1], second.bbox[3])
    side_by_side = _overlap(*vertical) >= MIN_OVERLAP * min(first.height, second.height) and -_overlap(*horizontal) <= word_gap
    return side_by_side or _stacked(first, second, stack_gap)


def _equals_pair(first: Component, second: Component, stack_gap: float) -> bool:
    shared = _overlap((first.bbox[0], first.bbox[2]), (second.bbox[0], second.bbox[2]))
    return shared >= EQUALS_ALIGNMENT * max(first.width, second.width) and _stacked(first, second, stack_gap)


def _stacked_bars(components: list[Component], body_height: float, stack_gap: float) -> list[Component]:
    bars = [component for component in components if _is_bar(component, body_height)]
    return [stroke for stroke in bars if any(other is not stroke and _equals_pair(stroke, other, stack_gap) for other in bars)]


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


def _band(components: list[Component]) -> tuple[int, int]:
    top = min(component.bbox[1] for component in components)
    depth = np.zeros(max(component.bbox[3] for component in components) - top, dtype=int)
    for component in components:
        depth[component.bbox[1] - top:component.bbox[3] - top] += 1
    if depth.max() < MAJORITY_DEPTH:
        tallest = max(components, key=lambda component: component.height)
        return tallest.bbox[1], tallest.bbox[3]
    shared = np.concatenate(([0], (depth * 2 >= depth.max()).astype(int), [0]))
    edges = np.flatnonzero(np.diff(shared))
    start, end = max(zip(edges[::2], edges[1::2]), key=lambda run: int(depth[run[0]:run[1]].sum()))
    return top + int(start), top + int(end)


def _classify(component: Component, band: tuple[int, int]) -> Band:
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


def _rests_on_another(item: Component, others: list[Component]) -> bool:
    centre = (item.bbox[1] + item.bbox[3]) / 2
    return any(other is not item and other.height > item.height and centre < other.bbox[1] + RESTING_DEPTH * other.height
               and _overlap((item.bbox[0], item.bbox[2]), (other.bbox[0], other.bbox[2])) >= RESTING_OVERLAP * item.width
               for other in others)


def _drawing_order(placed: list[Placed]) -> tuple[Placed, ...]:
    main = [item.component for item in placed if item.band is Band.MAIN]
    resting = {id(item) for item in placed if item.band is Band.MAIN and _rests_on_another(item.component, main)}
    hosts = sorted((item for item in placed if item.band is Band.MAIN and id(item) not in resting), key=lambda item: item.component.bbox[0])
    marks = sorted((item for item in placed if item.band is not Band.MAIN or id(item) in resting),
                   key=lambda item: (item.band is Band.BELOW, item.component.bbox[0]))
    if not hosts:
        return tuple(sorted(marks, key=lambda item: item.component.bbox[0]))
    attached: list[list[Placed]] = [[] for _ in hosts]
    for mark in marks:
        attached[_host(mark.component, hosts)].append(mark)
    return tuple(item for host, own in zip(hosts, attached) for item in (host, *own))


def page_words(components: list[Component], body_height: float, word_gap: float, stack_gap: float) -> list[list[ScanWord]]:
    equals = _stacked_bars(components, body_height, stack_gap * body_height)
    in_equals = {id(stroke) for stroke in equals}
    letters = [component for component in components if id(component) not in in_equals]
    words = []
    for group in _groups(letters, word_gap * body_height, stack_gap * body_height) + _groups(equals, 0, stack_gap * body_height):
        band = _band(group)
        words.append(ScanWord(_drawing_order([Placed(component, _classify(component, band)) for component in group]), band))
    return _lines(words)


def _line_band(line: list[ScanWord]) -> tuple[int, int]:
    return min(word.band[0] for word in line), max(word.band[1] for word in line)


def _lines(words: list[ScanWord]) -> list[list[ScanWord]]:
    lines: list[list[ScanWord]] = []
    for word in sorted(words, key=lambda item: item.band[0]):
        height = word.band[1] - word.band[0]
        line = next((line for line in lines if _overlap(_line_band(line), word.band) >= MAIN_OVERLAP * height), None)
        if line is None:
            lines.append([word])
        else:
            line.append(word)
    return [sorted(line, key=lambda item: item.bbox[0]) for line in lines]
